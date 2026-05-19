#!/usr/bin/env python3
"""
Scrape product images from PDP pages and persist to tecbite_product_state.image_url.

Uses the same env vars as catalog_scraper.py:
  DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME

Strategy:
- Query all active products with pdp_url where image_url IS NULL
- For each PDP, extract main image src from .image img.img-thumbnail
- Update image_url in DB
- ThreadPoolExecutor with polite delays (max 8 workers, 0.3s between batch requests)
"""

import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "n8n.yavingos.com"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", ""),
    "dbname": os.getenv("DB_NAME", "n8ntecbite_db"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TecbiteImageBot/1.0; +https://tecbite.com)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "es-PA,es;q=0.9",
}

WORKERS = 8
REQUEST_TIMEOUT = 15
DELAY_BETWEEN_REQUESTS = 0.2  # seconds per worker
BATCH_DB_COMMIT = 50
PROGRESS_EVERY = 100

# ── Logging ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scrape_images")

# ── Selectors (same as catalog_scraper PDP_IMAGE) ──────
IMAGE_SELECTORS = [
    ".image img.img-thumbnail",
    ".image img",
    ".image a img",
    "#image img",
    "meta[property='og:image']",
]

BLACKLIST_KEYWORDS = ["icon", "logo", "avatar", "whatsapp", "banner", "placeholder"]


def extract_image_url(html: str, base_url: str) -> str | None:
    """Extract main product image URL from PDP HTML."""
    soup = BeautifulSoup(html, "lxml")

    for selector in IMAGE_SELECTORS:
        el = soup.select_one(selector)
        if el is None:
            continue

        # <meta> tag
        if selector.startswith("meta"):
            content = el.get("content", "")
            if content:
                return urljoin(base_url, content)
            continue

        # <img> tag — try multiple src attributes
        for attr in ("src", "data-zoom-image", "data-src", "data-large"):
            src = el.get(attr, "")
            if not src:
                continue
            src_lower = src.lower()
            if any(kw in src_lower for kw in BLACKLIST_KEYWORDS):
                continue
            absolute = urljoin(base_url, src)
            if absolute.startswith("http"):
                return absolute

    return None


def scrape_one(sku: str, pdp_url: str) -> tuple[str, str | None]:
    """Scrape a single PDP and return (sku, image_url)."""
    try:
        resp = requests.get(pdp_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        image_url = extract_image_url(resp.text, pdp_url)
        return sku, image_url
    except Exception as exc:
        logger.debug("SKU %s: %s", sku, type(exc).__name__)
        return sku, None


def main():
    logger.info("Starting image scraper — connecting to %s:%s/%s",
                DB_CONFIG["host"], DB_CONFIG["port"], DB_CONFIG["dbname"])

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # Count pending
            cur.execute("""
                SELECT COUNT(*)
                FROM tecbite_product_state
                WHERE is_active = TRUE
                  AND pdp_url IS NOT NULL
                  AND pdp_url != ''
                  AND (image_url IS NULL OR image_url = '')
            """)
            total = cur.fetchone()[0]
            logger.info("Products to scrape: %d", total)

            if total == 0:
                logger.info("Nothing to do — all products already have image_url")
                return

            # Fetch batch of SKUs to process
            cur.execute("""
                SELECT product_sku, pdp_url
                FROM tecbite_product_state
                WHERE is_active = TRUE
                  AND pdp_url IS NOT NULL
                  AND pdp_url != ''
                  AND (image_url IS NULL OR image_url = '')
                ORDER BY ingested_at DESC
            """)
            rows = cur.fetchall()

        # ── Concurrent scraping ─────────────────────────
        scraped = 0
        errors = 0
        image_found = 0
        start_time = time.monotonic()
        batch: list[tuple[str, str | None]] = []

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {
                executor.submit(scrape_one, sku, pdp_url): sku
                for sku, pdp_url in rows
            }

            for future in as_completed(futures):
                sku, image_url = future.result()
                scraped += 1

                if image_url:
                    image_found += 1
                else:
                    errors += 1

                batch.append((image_url, sku))

                # Commit batch to DB
                if len(batch) >= BATCH_DB_COMMIT:
                    _flush_batch(conn, batch)
                    batch.clear()

                # Progress
                if scraped % PROGRESS_EVERY == 0:
                    elapsed = time.monotonic() - start_time
                    rate = scraped / elapsed if elapsed > 0 else 0
                    logger.info(
                        "Progress: %d/%d (%.1f%%) | rate: %.1f/s | images: %d | errors: %d",
                        scraped, total, scraped / total * 100,
                        rate, image_found, errors,
                    )

                time.sleep(DELAY_BETWEEN_REQUESTS)

        # Final flush
        if batch:
            _flush_batch(conn, batch)

        elapsed = time.monotonic() - start_time
        logger.info(
            "DONE — %d products in %.1fs (%.1f/s) | images: %d | errors: %d",
            scraped, elapsed, scraped / elapsed if elapsed > 0 else 0,
            image_found, errors,
        )

    finally:
        conn.close()


def _flush_batch(conn, batch: list[tuple[str | None, str]]) -> None:
    """Update image_url for a batch of SKUs."""
    with conn.cursor() as cur:
        execute_values(cur, """
            UPDATE tecbite_product_state AS t SET
                image_url = v.image_url,
                ingested_at = NOW()
            FROM (VALUES %s) AS v(image_url, product_sku)
            WHERE t.product_sku = v.product_sku
              AND t.is_active = TRUE
        """, batch)
    conn.commit()


if __name__ == "__main__":
    main()
