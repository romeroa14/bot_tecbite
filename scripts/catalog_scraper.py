#!/usr/bin/env python3
"""
Tecbite Catalog Scraper — OpenCart PDP Extractor
═══════════════════════════════════════════════════
Descubre productos desde listing pages, extrae datos de PDPs
y los inserta en tecbite_product_state vía UPSERT.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

# ═══════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════
BASE_URL = "https://catalog.tecbite.com/index.php"
CATEGORY_ROUTE = "product/category"
SOURCE_HOST = "catalog.tecbite.com"
DEFAULT_CURRENCY = "USD"
DEFAULT_LOCALE = "es-cl"
PRODUCTS_PER_PAGE = 48
DEFAULT_DELAY = 2.0
DEFAULT_RETRIES = 3
DEFAULT_TIMEOUT = 30
MIN_PDP_SIZE = 200
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 TecbiteCatalog/2.0"
)

# ═══════════════════════════════════════════════════════
# CSS SELECTORS (validated against live HTML)
# ═══════════════════════════════════════════════════════

# ── LISTING PAGE ──
LISTING_CARD = ".product-thumb"
LISTING_LINK = ".image a, .description h4 a"
LISTING_TITLE = ".description h4 a"
LISTING_PRICE = ".price .price-new"
LISTING_IMAGE = ".image img"
LISTING_PRODUCT_ID = 'input[name="product_id"]'
LISTING_PAGINATION = ".pagination a"

# ── PDP ──
PDP_TITLE = "h1"
PDP_LIST_ITEMS = "ul.list-unstyled li"
PDP_PRICE = ".price-new, h2 .price-new"
PDP_IMAGE = ".image img, .image a img"
PDP_DESCRIPTION = "#tab-description"
PDP_SPEC_TABLE = "#tab-specification table tr"
PDP_BREADCRUMB = ".breadcrumb li a"
PDP_TAGS = "p a[href*='tag=']"

# ── REMOVABLE (noise) ──
REMOVABLE = ["script", "style", "noscript", "header", "footer", "nav"]

# ── CATEGORIES TO TARGET (all Automotriz, fallback when sitemap fails) ──
AUTOMOTIVE_CATEGORIES = {
    "3_31",    # Barras de Techo
    "3_32",    # Portabicicletas
    "3_33",    # Baules y canasta
    "3_34",    # Deportes Aquaticos
    "3_35",    # TRACRAC
    "3_36",    # Accesorios Thule
    "3_5139",  # Alfombras (WeatherTech FloorLiners)
    "3_5175",  # Tepui
    "3_5176",  # Limpieza y Mantenimiento
    "3_5180",  # Deflectores (WeatherTech)
    "3_5181",  # Sistemas de Remolque (CURT)
}
# Backward compat alias
THULE_CATEGORIES = AUTOMOTIVE_CATEGORIES

logger = logging.getLogger("catalog_scraper")


# ═══════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════

@dataclass
class Category:
    path: str
    name: str
    depth: int


@dataclass
class ProductLink:
    product_id: str
    title_hint: str
    pdp_url: str
    listing_url: str
    image_url: Optional[str]
    listing_price: Optional[Decimal]


@dataclass
class ProductData:
    snapshot_id: str
    product_sku: str
    listing_url: Optional[str]
    pdp_url: str
    source_url: str
    title: str
    brand: Optional[str]
    category: Optional[str]
    price_amount: Optional[Decimal]
    currency: str
    stock_status: Optional[str]
    promo_text: Optional[str]
    attributes: Dict[str, str]
    source_updated_at: datetime
    fresh_until: datetime
    content_hash: str
    provenance: Dict[str, str]
    extraction_error: Optional[str] = None


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def normalize(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def parse_price(raw: Optional[str]) -> Optional[Decimal]:
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9,.\-]", "", raw).replace(",", ".")
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def build_category_url(path: str, page: int = 1, limit: int = PRODUCTS_PER_PAGE) -> str:
    params = {
        "route": CATEGORY_ROUTE,
        "language": DEFAULT_LOCALE,
        "path": path,
        "limit": limit,
    }
    if page > 1:
        params["page"] = page
    return f"{BASE_URL}?{urlencode(params)}"


def build_db_url() -> str:
    return (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


# ═══════════════════════════════════════════════════════
# CATALOG SCRAPER
# ═══════════════════════════════════════════════════════

class CatalogScraper:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.engine = create_engine(build_db_url(), pool_pre_ping=True)
        self.snapshot_id = str(uuid.uuid4())
        self.now = datetime.now(timezone.utc)
        self.fresh_until = self.now + timedelta(hours=self.args.freshness_hours)
        self.stats = {"categories": 0, "listings": 0, "pdps_fetched": 0,
                      "pdps_extracted": 0, "pdps_skipped": 0, "errors": 0,
                      "inserted": 0, "updated": 0}

    # ── HTTP ─────────────────────────────────────────

    def get(self, url: str) -> requests.Response:
        last_err = None
        for attempt in range(self.args.retries):
            try:
                resp = self.session.get(url, timeout=self.args.timeout)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 30))
                    logger.warning("Rate limited (429). Waiting %ds...", retry_after)
                    time.sleep(retry_after)
                    continue
                if 500 <= resp.status_code < 600:
                    raise requests.HTTPError(f"Server error {resp.status_code}", response=resp)
                return resp
            except Exception as exc:
                last_err = exc
                wait = 2 ** attempt + 1
                logger.warning("HTTP attempt %d/%d failed: %s. Retry in %ds...",
                               attempt + 1, self.args.retries, exc, wait)
                time.sleep(wait)
        raise last_err  # type: ignore[misc]

    # ── CATEGORY DISCOVERY ────────────────────────────

    def discover_categories(self) -> List[Category]:
        cats: List[Category] = []
        seen: Set[str] = set()
        sitemap_url = f"{BASE_URL}?route=information/sitemap&language={DEFAULT_LOCALE}"

        try:
            resp = self.get(sitemap_url)
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select("a[href*='path=']"):
                href = a.get("href", "")
                m = re.search(r"path=([\d_]+)", href)
                if not m:
                    continue
                path = m.group(1)
                if path in seen:
                    continue
                seen.add(path)
                depth = path.count("_") + 1
                name = normalize(a.get_text(" ", strip=True))
                if not name:
                    continue

                if self.args.categories:
                    # Exact match OR path starts with "parent_" (child of specified parent)
                    if path not in self.args.categories and not any(
                        path.startswith(f"{c}_") for c in self.args.categories
                    ):
                        continue

                cats.append(Category(path=path, name=name, depth=depth))

        except Exception as exc:
            logger.warning("Category discovery from sitemap failed: %s", exc)
            # Fallback: use predefined categories
            if self.args.categories:
                for c in self.args.categories:
                    cats.append(Category(path=c, name=f"Category {c}", depth=c.count("_") + 1))
            else:
                for c in THULE_CATEGORIES:
                    cats.append(Category(path=c, name=f"Category {c}", depth=c.count("_") + 1))

        logger.info("Discovered %d categories", len(cats))
        return cats

    # ── LISTING CRAWL ─────────────────────────────────

    def crawl_listing(self, category: Category) -> List[ProductLink]:
        products: List[ProductLink] = []
        listing_url = build_category_url(category.path)

        page = 1
        while True:
            page_url = build_category_url(category.path, page=page)

            try:
                resp = self.get(page_url)
            except Exception as exc:
                logger.error("Failed to fetch listing %s: %s", page_url, exc)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(LISTING_CARD)

            if not cards:
                break  # No more products on this page

            for card in cards:
                try:
                    link_el = card.select_one(LISTING_LINK)
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    if not href:
                        continue

                    title_el = card.select_one(LISTING_TITLE)
                    title = normalize(title_el.get_text(" ", strip=True)) if title_el else ""

                    pid_input = card.select_one(LISTING_PRODUCT_ID)
                    pid = pid_input.get("value", "") if pid_input else ""

                    img_el = card.select_one(LISTING_IMAGE)
                    img_url = img_el.get("src") if img_el else None

                    price_el = card.select_one(LISTING_PRICE)
                    listing_price = parse_price(price_el.get_text(strip=True)) if price_el else None

                    absolute_url = urljoin(page_url, href)

                    products.append(ProductLink(
                        product_id=pid,
                        title_hint=title,
                        pdp_url=absolute_url,
                        listing_url=page_url,
                        image_url=img_url,
                        listing_price=listing_price,
                    ))
                except Exception:
                    continue

            logger.info("  Page %d: %d products (%d total in %s)",
                        page, len(cards), len(products), category.name)

            if len(cards) < PRODUCTS_PER_PAGE:
                break  # Last page

            if self.args.max_pages and page >= self.args.max_pages:
                break

            page += 1
            time.sleep(self.args.delay)

        self.stats["listings"] += len(products)
        return products

    # ── PDP EXTRACTION ────────────────────────────────

    def extract_pdp(self, html: str, url: str, link: ProductLink) -> ProductData:
        soup = BeautifulSoup(html, "lxml")

        # ── Remove noise ──
        for sel in REMOVABLE:
            for node in soup.select(sel):
                node.decompose()

        # ── Title ──
        h1 = soup.select_one(PDP_TITLE)
        title = normalize(h1.get_text(" ", strip=True)) if h1 else link.title_hint

        # ── SKU ──
        sku = ""
        for li in soup.select(PDP_LIST_ITEMS):
            text = normalize(li.get_text(" ", strip=True))
            if "Código del producto:" in text:
                sku = text.split("Código del producto:", 1)[1].strip()
                break
        if not sku:
            sku = link.product_id or re.sub(r"[^A-Za-z0-9\-_]", "", title[:20])

        # ── Brand ──
        brand = ""
        for li in soup.select(PDP_LIST_ITEMS):
            text = normalize(li.get_text(" ", strip=True))
            if "Marca:" in text:
                a_tag = li.select_one("a")
                brand = normalize(a_tag.get_text(strip=True)) if a_tag else text.split("Marca:", 1)[1].strip()
                break

        # ── Category (breadcrumb) ──
        crumbs = []
        for a in soup.select(PDP_BREADCRUMB):
            t = normalize(a.get_text(" ", strip=True))
            if t and t.lower() != "home" and not a.select_one("i"):
                crumbs.append(t)
        category = " > ".join(crumbs) if crumbs else None

        # ── Price ──
        price_el = soup.select_one(PDP_PRICE)
        price = parse_price(normalize(price_el.get_text(strip=True))) if price_el else link.listing_price

        # ── Stock ──
        stock_status = "discontinued"
        for li in soup.select(PDP_LIST_ITEMS):
            text = normalize(li.get_text(" ", strip=True))
            if "Disponibilidad:" in text:
                val = text.split("Disponibilidad:", 1)[1].strip()
                n = int(val) if val.isdigit() else -1
                stock_status = "in_stock" if n > 0 else ("out_of_stock" if n == 0 else "discontinued")
                break

        # ── Description ──
        desc_el = soup.select_one(PDP_DESCRIPTION)
        description = normalize(desc_el.get_text(" ", strip=True)) if desc_el else ""

        # ── Images ──
        images = []
        for img in soup.select(PDP_IMAGE):
            src = img.get("src", "")
            if src and not any(x in src.lower() for x in ["icon", "logo", "avatar", "whatsapp"]):
                absolute = urljoin(url, src)
                if absolute not in images:
                    images.append(absolute)

        # ── Attributes / Specs ──
        attributes: Dict[str, str] = {}
        for row in soup.select(PDP_SPEC_TABLE):
            cells = row.select("td")
            if len(cells) >= 2:
                key = normalize(cells[0].get_text(" ", strip=True))
                val = normalize(cells[1].get_text(" ", strip=True))
                if key and val:
                    attributes[key] = val

        # ── Promo text ──
        promo = None
        badge = soup.select_one(".product-badge, .price__badge-sale, [class*='promo']")
        if badge:
            promo = normalize(badge.get_text(" ", strip=True))

        # ── Content hash ──
        hash_payload = f"{sku}|{title}|{price}|{stock_status}"
        content_hash = sha256_hex(hash_payload)

        # ── Provenance ──
        provenance = {
            "listing_url": link.listing_url,
            "pdp_url": url,
            "retrieved_at": self.now.isoformat(),
            "product_id": link.product_id,
        }

        return ProductData(
            snapshot_id=self.snapshot_id,
            product_sku=sku,
            listing_url=link.listing_url,
            pdp_url=url,
            source_url=url,
            title=title,
            brand=brand or None,
            category=category,
            price_amount=price,
            currency=DEFAULT_CURRENCY,
            stock_status=stock_status,
            promo_text=promo,
            attributes=attributes,
            source_updated_at=self.now,
            fresh_until=self.fresh_until,
            content_hash=content_hash,
            provenance=provenance,
        )

    def fetch_and_extract(self, link: ProductLink) -> Optional[ProductData]:
        try:
            resp = self.get(link.pdp_url)
            self.stats["pdps_fetched"] += 1

            if resp.status_code >= 400:
                logger.warning("PDP %s returned HTTP %d", link.pdp_url, resp.status_code)
                self.stats["pdps_skipped"] += 1
                return None

            if len(resp.text) < MIN_PDP_SIZE:
                logger.warning("PDP %s too small (%d bytes)", link.pdp_url, len(resp.text))
                self.stats["pdps_skipped"] += 1
                return None

            product = self.extract_pdp(resp.text, resp.url, link)
            self.stats["pdps_extracted"] += 1
            return product

        except Exception as exc:
            logger.error("PDP fetch failed for %s: %s", link.pdp_url, exc)
            self.stats["errors"] += 1
            return None

    # ── PERSISTENCE ───────────────────────────────────

    def persist_snapshot(self, count: int) -> None:
        batch_hash = sha256_hex(f"{self.snapshot_id}|{count}")
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO tecbite_catalog_snapshot (
                    snapshot_id, snapshot_at, crawl_started_at, crawl_finished_at,
                    status, source_host, batch_hash
                ) VALUES (
                    :sid, :sat, :sat, NOW(),
                    'success', :host, :hash
                )
                ON CONFLICT (batch_hash) DO NOTHING
            """), {
                "sid": self.snapshot_id, "sat": self.now,
                "host": SOURCE_HOST, "hash": batch_hash,
            })
        logger.info("Snapshot %s persisted", self.snapshot_id[:8])

    def persist_batch(self, products: List[ProductData]) -> Tuple[int, int]:
        inserted, updated = 0, 0
        with self.engine.begin() as conn:
            for p in products:
                result = conn.execute(text("""
                    INSERT INTO tecbite_product_state (
                        snapshot_id, product_sku, listing_url, pdp_url, source_url,
                        title, brand, category, price_amount, currency,
                        stock_status, promo_text, attributes,
                        source_updated_at, fresh_until, content_hash,
                        provenance, ingested_at, is_active
                    ) VALUES (
                        :snapshot_id, :product_sku, :listing_url, :pdp_url, :source_url,
                        :title, :brand, :category, :price_amount, :currency,
                        :stock_status, :promo_text, CAST(:attributes AS jsonb),
                        :source_updated_at, :fresh_until, :content_hash,
                        CAST(:provenance AS jsonb), :ingested_at, TRUE
                    )
                    ON CONFLICT (snapshot_id, product_sku)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        brand = EXCLUDED.brand,
                        category = EXCLUDED.category,
                        price_amount = EXCLUDED.price_amount,
                        stock_status = EXCLUDED.stock_status,
                        promo_text = EXCLUDED.promo_text,
                        attributes = EXCLUDED.attributes,
                        source_updated_at = EXCLUDED.source_updated_at,
                        fresh_until = EXCLUDED.fresh_until,
                        content_hash = EXCLUDED.content_hash,
                        provenance = EXCLUDED.provenance,
                        ingested_at = EXCLUDED.ingested_at,
                        is_active = TRUE
                    RETURNING (xmax = 0) AS is_insert
                """), {
                    "snapshot_id": p.snapshot_id,
                    "product_sku": p.product_sku,
                    "listing_url": p.listing_url,
                    "pdp_url": p.pdp_url,
                    "source_url": p.source_url,
                    "title": p.title,
                    "brand": p.brand,
                    "category": p.category,
                    "price_amount": str(p.price_amount) if p.price_amount else None,
                    "currency": p.currency,
                    "stock_status": p.stock_status,
                    "promo_text": p.promo_text,
                    "attributes": json.dumps(p.attributes, ensure_ascii=True),
                    "source_updated_at": p.source_updated_at,
                    "fresh_until": p.fresh_until,
                    "content_hash": p.content_hash,
                    "provenance": json.dumps(p.provenance, ensure_ascii=True),
                    "ingested_at": p.source_updated_at,
                })
                is_insert = result.scalar()
                if is_insert:
                    inserted += 1
                else:
                    updated += 1
        return inserted, updated

    # ── MAIN PIPELINE ─────────────────────────────────

    def run(self) -> None:
        logger.info("=" * 60)
        logger.info("CATALOG SCRAPER STARTING — snapshot %s", self.snapshot_id[:8])
        logger.info("=" * 60)

        # 1. Discover categories
        categories = self.discover_categories()
        if not categories:
            logger.error("No categories to crawl. Exiting.")
            return

        # 2. Sort: depth-first (subcategories first for freshness)
        categories.sort(key=lambda c: (-c.depth, c.path))

        all_products: List[ProductData] = []

        for cat in categories:
            indent = "  " * (cat.depth - 1)
            logger.info("%s[%s] %s", indent, cat.path, cat.name)
            self.stats["categories"] += 1

            # 2a. Crawl listing
            links = self.crawl_listing(cat)
            if self.args.dry_run:
                for l in links[:3]:
                    logger.info("%s  → [%s] %s", indent, l.product_id, l.title_hint[:60])
                continue

            # 2b. Fetch & extract PDPs
            for link in links:
                if self.args.max_products and self.stats["pdps_fetched"] >= self.args.max_products:
                    break

                product = self.fetch_and_extract(link)
                if product:
                    all_products.append(product)

                # 2c. Batch persist
                if len(all_products) >= self.args.batch_size:
                    ins, upd = self.persist_batch(all_products)
                    self.stats["inserted"] += ins
                    self.stats["updated"] += upd
                    logger.info("  💾 Batch: %d inserted, %d updated (total: %d)",
                                ins, upd, self.stats["inserted"] + self.stats["updated"])
                    all_products.clear()

                time.sleep(self.args.delay)

            if self.args.max_products and self.stats["pdps_fetched"] >= self.args.max_products:
                break

        # 3. Final batch
        if all_products:
            ins, upd = self.persist_batch(all_products)
            self.stats["inserted"] += ins
            self.stats["updated"] += upd
            logger.info("  💾 Final batch: %d inserted, %d updated", ins, upd)

        # 4. Persist snapshot
        if not self.args.dry_run:
            self.persist_snapshot(self.stats["inserted"] + self.stats["updated"])

        # 5. Summary
        logger.info("=" * 60)
        logger.info("SCRAPE COMPLETE")
        logger.info("  Categories:    %d", self.stats["categories"])
        logger.info("  Listings:      %d", self.stats["listings"])
        logger.info("  PDPs fetched:  %d", self.stats["pdps_fetched"])
        logger.info("  PDPs extracted:%d", self.stats["pdps_extracted"])
        logger.info("  PDPs skipped:  %d", self.stats["pdps_skipped"])
        logger.info("  Errors:        %d", self.stats["errors"])
        logger.info("  Inserted:      %d", self.stats["inserted"])
        logger.info("  Updated:       %d", self.stats["updated"])
        logger.info("=" * 60)

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════

def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tecbite Catalog Scraper — OpenCart PDP extractor"
    )
    parser.add_argument("--categories", nargs="*",
                        help="Category paths to scrape (default: Thule categories)")
    parser.add_argument("--max-pages", type=int, default=0,
                        help="Max listing pages per category (0=all)")
    parser.add_argument("--max-products", type=int, default=0,
                        help="Max total PDPs to fetch (0=all)")
    parser.add_argument("--batch-size", type=int, default=25,
                        help="Products per DB commit")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="Delay between requests in seconds")
    parser.add_argument("--freshness-hours", type=int, default=12,
                        help="fresh_until offset in hours")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                        help="HTTP retries per request")
    parser.add_argument("--dry-run", action="store_true",
                        help="Crawl only, no DB writes")
    parser.add_argument("--log-level", default="INFO",
                        choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    scraper = CatalogScraper(args)
    try:
        scraper.run()
        return 0
    except KeyboardInterrupt:
        logger.warning("Scraping interrupted by user")
        return 130
    except Exception:
        logger.exception("Fatal error in catalog scraper")
        return 1
    finally:
        scraper.close()


if __name__ == "__main__":
    sys.exit(main())
