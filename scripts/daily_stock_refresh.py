#!/usr/bin/env python3
"""
Daily Stock Refresh — Lightweight listing-only updater
═══════════════════════════════════════════════════════
Recorre las listing pages de TODAS las categorías de Automotriz
y actualiza price_amount + stock_status en tecbite_product_state
sin necesidad de visitar cada PDP individual.

Diseñado para correr diariamente via cron o n8n.

Uso:
  python3 daily_stock_refresh.py                # producción
  python3 daily_stock_refresh.py --dry-run      # solo log, no DB
  python3 daily_stock_refresh.py --delay 3      # más lento (respetar rate limits)
"""

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# ═══════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════
BASE_URL = "https://catalog.tecbite.com/index.php"
DEFAULT_LOCALE = "es-cl"
PRODUCTS_PER_PAGE = 100  # Máximo de OpenCart para menos requests
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 TecbiteStockBot/1.0"
)

# Todas las categorías de Automotriz (completas, incluyendo las 4 faltantes)
ALL_AUTOMOTIVE_CATEGORIES = {
    "3_31":   "Barras de Techo",
    "3_32":   "Portabicicletas",
    "3_33":   "Baules y canasta",
    "3_34":   "Deportes Aquaticos",
    "3_35":   "TRACRAC",
    "3_36":   "Accesorios Thule",
    "3_5139": "Alfombras",
    "3_5175": "Tepui",
    "3_5176": "Limpieza y Mantenimiento",
    "3_5180": "Deflectores",
    "3_5181": "Sistemas de Remolque",
}

logger = logging.getLogger("stock_refresh")


# ═══════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════

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


def build_db_url() -> str:
    return (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


def build_listing_url(path: str, page: int = 1) -> str:
    params = {
        "route": "product/category",
        "language": DEFAULT_LOCALE,
        "path": path,
        "limit": PRODUCTS_PER_PAGE,
    }
    if page > 1:
        params["page"] = page
    return f"{BASE_URL}?{urlencode(params)}"


# ═══════════════════════════════════════════════════
# STOCK REFRESHER
# ═══════════════════════════════════════════════════

class StockRefresher:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.engine = create_engine(build_db_url(), pool_pre_ping=True)
        self.now = datetime.now(timezone.utc)
        self.stats = {
            "categories": 0,
            "pages": 0,
            "products_seen": 0,
            "updated": 0,
            "not_found": 0,
            "errors": 0,
        }

    def get(self, url: str, retries: int = 3) -> requests.Response:
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 30))
                    logger.warning("Rate limited. Waiting %ds...", wait)
                    time.sleep(wait)
                    continue
                return resp
            except Exception as exc:
                wait = 2 ** attempt + 1
                logger.warning("HTTP error (attempt %d): %s", attempt + 1, exc)
                time.sleep(wait)
        raise ConnectionError(f"Failed after {retries} retries: {url}")

    def extract_listing_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extrae SKU aproximado, precio y stock desde las tarjetas de listing."""
        products = []
        for card in soup.select(".product-thumb"):
            try:
                # Título → usamos para buscar en DB
                title_el = card.select_one(".description h4 a")
                title = title_el.get_text(" ", strip=True) if title_el else ""

                # Precio
                price_el = card.select_one(".price .price-new")
                if not price_el:
                    price_el = card.select_one(".price")
                price = parse_price(price_el.get_text(strip=True)) if price_el else None

                # Stock: OpenCart muestra "Add to Cart" solo si hay stock
                # También puede tener "Out of Stock" badge
                cart_btn = card.select_one("button[onclick*='cart.add'], .button-group button")
                stock_badge = card.select_one(".out-of-stock, [class*='stock']")

                if stock_badge and "out" in stock_badge.get_text(strip=True).lower():
                    stock_status = "out_of_stock"
                elif cart_btn:
                    stock_status = "in_stock"
                else:
                    stock_status = None  # No cambiar si no estamos seguros

                # Product ID del input hidden
                pid_input = card.select_one('input[name="product_id"]')
                product_id = pid_input.get("value", "") if pid_input else ""

                # Link al PDP (para matching)
                link_el = card.select_one(".image a, .description h4 a")
                pdp_url = link_el.get("href", "") if link_el else ""

                products.append({
                    "title": title,
                    "price": price,
                    "stock_status": stock_status,
                    "product_id": product_id,
                    "pdp_url": pdp_url,
                })
            except Exception:
                continue

        return products

    def update_stock_in_db(self, products: List[Dict]) -> Tuple[int, int]:
        """Actualiza precio y stock en tecbite_product_state matcheando por título."""
        updated = 0
        not_found = 0

        with self.engine.begin() as conn:
            for p in products:
                if not p["title"]:
                    continue

                # Intentar matchear por título exacto (más confiable que product_id)
                set_clauses = []
                params = {
                    "title": p["title"],
                    "now": self.now,
                }

                if p["price"] is not None:
                    set_clauses.append("price_amount = :price")
                    params["price"] = str(p["price"])

                if p["stock_status"] is not None:
                    set_clauses.append("stock_status = :stock")
                    params["stock"] = p["stock_status"]

                if not set_clauses:
                    continue

                set_clauses.append("source_updated_at = :now")

                sql = f"""
                    UPDATE tecbite_product_state
                    SET {', '.join(set_clauses)}
                    WHERE title = :title AND is_active = true
                """
                result = conn.execute(text(sql), params)

                if result.rowcount > 0:
                    updated += result.rowcount
                else:
                    not_found += 1
                    logger.debug("No match for: %s", p["title"][:60])

        return updated, not_found

    def refresh_category(self, path: str, name: str) -> None:
        """Recorre todas las páginas de una categoría y actualiza stock."""
        page = 1
        while True:
            url = build_listing_url(path, page=page)
            try:
                resp = self.get(url)
            except Exception as exc:
                logger.error("Failed to fetch %s page %d: %s", name, page, exc)
                self.stats["errors"] += 1
                break

            soup = BeautifulSoup(resp.text, "lxml")
            products = self.extract_listing_data(soup)

            if not products:
                break

            self.stats["products_seen"] += len(products)
            self.stats["pages"] += 1

            if not self.args.dry_run:
                updated, not_found = self.update_stock_in_db(products)
                self.stats["updated"] += updated
                self.stats["not_found"] += not_found
                logger.info("  Page %d: %d products → %d updated, %d not found",
                            page, len(products), updated, not_found)
            else:
                logger.info("  Page %d: %d products (dry-run)", page, len(products))
                for p in products[:3]:
                    logger.info("    → %s | $%s | %s",
                                p["title"][:50], p["price"], p["stock_status"])

            if len(products) < PRODUCTS_PER_PAGE:
                break

            page += 1
            time.sleep(self.args.delay)

    def run(self) -> None:
        logger.info("=" * 60)
        logger.info("DAILY STOCK REFRESH — %s", self.now.strftime("%Y-%m-%d %H:%M UTC"))
        logger.info("=" * 60)

        for path, name in sorted(ALL_AUTOMOTIVE_CATEGORIES.items()):
            logger.info("[%s] %s", path, name)
            self.stats["categories"] += 1
            self.refresh_category(path, name)
            time.sleep(self.args.delay)

        logger.info("=" * 60)
        logger.info("REFRESH COMPLETE")
        logger.info("  Categories:    %d", self.stats["categories"])
        logger.info("  Pages crawled: %d", self.stats["pages"])
        logger.info("  Products seen: %d", self.stats["products_seen"])
        logger.info("  DB updated:    %d", self.stats["updated"])
        logger.info("  Not found:     %d", self.stats["not_found"])
        logger.info("  Errors:        %d", self.stats["errors"])
        logger.info("=" * 60)

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Daily stock price refresh from listing pages")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Log only, no DB writes")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    refresher = StockRefresher(args)
    try:
        refresher.run()
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130
    except Exception:
        logger.exception("Fatal error")
        return 1
    finally:
        refresher.close()


if __name__ == "__main__":
    sys.exit(main())
