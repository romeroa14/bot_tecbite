import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
except Exception:  # noqa: BLE001
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]

    class SQLAlchemyError(Exception):
        """Fallback SQLAlchemy error type when dependency is missing."""


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = (2, 8, 20)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 TecbiteCatalogETL/1.0"
)

DEFAULT_LISTING_SEEDS = (
    "https://www.tecbite.com/collections/thule",
    "https://www.tecbite.com/collections/portaequipaje",
)
SOURCE_HOST = "www.tecbite.com"
DEFAULT_FRESHNESS_MINUTES = 30
DEFAULT_CURRENCY = "USD"

LISTING_CARD_SELECTORS = (
    "article.product-card",
    "div.product-item",
    "li.product",
    "div.grid-product",
)
LISTING_LINK_SELECTORS = (
    "a.product-card__link[href]",
    "a.product-item__title[href]",
    "a[href*='/products/']",
    "a[href*='/producto/']",
)
TITLE_SELECTORS = (
    "h1.product__title",
    "h1.product-title",
    "h1[itemprop='name']",
    "h1",
)
SKU_SELECTORS = (
    "[itemprop='sku']",
    ".product-sku",
    "[data-product-sku]",
)
PRICE_SELECTORS = (
    "[itemprop='price']",
    ".price .money",
    ".product-price",
    ".price",
)
PROMO_SELECTORS = (
    ".product-badge",
    ".price__badge-sale",
    ".promotion",
    "[class*='promo']",
)
STOCK_SELECTORS = (
    ".product-form__inventory",
    ".stock-status",
    "[data-stock-status]",
    "[class*='availability']",
)
ATTRIBUTE_SELECTORS = (
    "table tr",
    ".product__specs li",
    ".product-features li",
    ".product-meta__item",
)
JSON_LD_SELECTOR = "script[type='application/ld+json']"


@dataclass
class ProductRecord:
    product_sku: str
    listing_url: Optional[str]
    pdp_url: str
    source_url: str
    title: Optional[str]
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


def build_database_uri() -> str:
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASS", "Tecbite20$")
    db_host = os.getenv("DB_HOST", "n8n.yavingos.com")
    db_port = os.getenv("DB_PORT", "5433")
    db_name = os.getenv("DB_NAME", "n8ntecbite_db")
    return f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if not value:
        return None
    cleaned = re.sub(r"[^0-9,.\-]", "", value).replace(",", ".")
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def ensure_absolute(url: str, base_url: str) -> str:
    return urljoin(base_url, url)


def compute_hash(payload: Dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class TecbiteCatalogIngestor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.logger = logging.getLogger("tecbite_catalog_etl")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
        self.now = datetime.now(timezone.utc)
        self.fresh_until = self.now + timedelta(minutes=args.freshness_minutes)

    def get(self, url: str) -> requests.Response:
        error: Optional[Exception] = None
        for attempt in range(self.args.retries):
            try:
                response = self.session.get(url, timeout=self.args.timeout)
                if 500 <= response.status_code < 600:
                    raise requests.HTTPError(
                        f"{response.status_code} from {url}", response=response
                    )
                return response
            except Exception as exc:  # noqa: BLE001
                error = exc
                wait_seconds = DEFAULT_BACKOFF_SECONDS[min(attempt, len(DEFAULT_BACKOFF_SECONDS) - 1)]
                wait_seconds += random.uniform(0.1, 0.9)
                self.logger.warning(
                    "Request failed (%s/%s) %s: %s; retrying in %.1fs",
                    attempt + 1,
                    self.args.retries,
                    url,
                    exc,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
        assert error is not None
        raise error

    def extract_json_ld(self, soup: BeautifulSoup) -> List[dict]:
        parsed_docs: List[dict] = []
        for script in soup.select(JSON_LD_SELECTOR):
            raw = (script.string or "").strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                parsed_docs.append(payload)
            elif isinstance(payload, list):
                parsed_docs.extend([item for item in payload if isinstance(item, dict)])
        return parsed_docs

    def discover_listing_links(self, listing_url: str) -> List[Dict[str, Optional[str]]]:
        response = self.get(listing_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        products: Dict[str, Dict[str, Optional[str]]] = {}

        for card_selector in LISTING_CARD_SELECTORS:
            for card in soup.select(card_selector):
                link = None
                for link_selector in LISTING_LINK_SELECTORS:
                    candidate = card.select_one(link_selector)
                    if candidate and candidate.get("href"):
                        link = ensure_absolute(candidate["href"], response.url)
                        break
                if not link:
                    continue
                products.setdefault(
                    link,
                    {
                        "listing_url": listing_url,
                        "pdp_url": link,
                        "title_hint": normalize_space(card.get_text(" ", strip=True))[:200] or None,
                    },
                )

        for link_selector in LISTING_LINK_SELECTORS:
            for link_node in soup.select(link_selector):
                href = link_node.get("href")
                if not href:
                    continue
                absolute = ensure_absolute(href, response.url)
                if "/products/" not in absolute and "/producto/" not in absolute:
                    continue
                products.setdefault(
                    absolute,
                    {
                        "listing_url": listing_url,
                        "pdp_url": absolute,
                        "title_hint": normalize_space(link_node.get_text(" ", strip=True))[:200] or None,
                    },
                )

        discovered = list(products.values())
        self.logger.info("Discovered %s PDP links from %s", len(discovered), listing_url)
        return discovered

    def parse_product(self, listing_context: Dict[str, Optional[str]]) -> Optional[ProductRecord]:
        pdp_url = listing_context["pdp_url"]
        assert pdp_url is not None
        response = self.get(pdp_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        json_docs = self.extract_json_ld(soup)
        parsed_url = urlparse(response.url)
        canonical_url = response.url

        title = listing_context.get("title_hint")
        for selector in TITLE_SELECTORS:
            node = soup.select_one(selector)
            if node and node.get_text(strip=True):
                title = normalize_space(node.get_text(" ", strip=True))
                break

        sku = None
        for selector in SKU_SELECTORS:
            node = soup.select_one(selector)
            if node:
                sku = (
                    node.get("content")
                    or node.get("data-product-sku")
                    or node.get_text(strip=True)
                )
                sku = normalize_space(sku or "")
                if sku:
                    break
        if not sku:
            for payload in json_docs:
                sku = payload.get("sku") or payload.get("productID")
                if sku:
                    sku = normalize_space(str(sku))
                    break
        if not sku:
            tail = parsed_url.path.rstrip("/").split("/")[-1]
            sku = normalize_space(re.sub(r"[^A-Za-z0-9\-_.]", "", tail)).upper()

        if not sku:
            self.logger.warning("Skipping product without SKU: %s", pdp_url)
            return None

        price_amount: Optional[Decimal] = None
        for selector in PRICE_SELECTORS:
            node = soup.select_one(selector)
            if node:
                candidate = node.get("content") or node.get_text(strip=True)
                price_amount = parse_decimal(candidate)
                if price_amount is not None:
                    break
        if price_amount is None:
            for payload in json_docs:
                offer = payload.get("offers")
                if isinstance(offer, list) and offer:
                    offer = offer[0]
                if isinstance(offer, dict):
                    price_amount = parse_decimal(str(offer.get("price", "")))
                    if price_amount is not None:
                        break

        currency = DEFAULT_CURRENCY
        for payload in json_docs:
            offer = payload.get("offers")
            if isinstance(offer, list) and offer:
                offer = offer[0]
            if isinstance(offer, dict) and offer.get("priceCurrency"):
                currency = normalize_space(str(offer["priceCurrency"])).upper()
                break

        stock_status = None
        for selector in STOCK_SELECTORS:
            node = soup.select_one(selector)
            if node:
                stock_status = normalize_space(
                    node.get("content") or node.get("data-stock-status") or node.get_text(" ", strip=True)
                )
                if stock_status:
                    break
        if not stock_status:
            body_text = normalize_space(soup.get_text(" ", strip=True)).lower()
            if "agotado" in body_text or "out of stock" in body_text:
                stock_status = "out_of_stock"
            elif "en stock" in body_text or "available" in body_text:
                stock_status = "in_stock"

        promo_text = None
        for selector in PROMO_SELECTORS:
            node = soup.select_one(selector)
            if node and node.get_text(strip=True):
                promo_text = normalize_space(node.get_text(" ", strip=True))
                break

        brand = None
        category = None
        for payload in json_docs:
            if not brand and isinstance(payload.get("brand"), dict):
                brand = payload["brand"].get("name")
            if not brand and payload.get("brand"):
                brand = str(payload.get("brand"))
            if not category and payload.get("category"):
                category = str(payload.get("category"))
        brand = normalize_space(brand) if brand else None
        category = normalize_space(category) if category else None

        attributes: Dict[str, str] = {}
        for row in soup.select(ATTRIBUTE_SELECTORS[0]):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = normalize_space(cells[0].get_text(" ", strip=True))
                val = normalize_space(cells[1].get_text(" ", strip=True))
                if key and val:
                    attributes[key] = val

        if not attributes:
            for selector in ATTRIBUTE_SELECTORS[1:]:
                for node in soup.select(selector):
                    text_value = normalize_space(node.get_text(" ", strip=True))
                    if not text_value:
                        continue
                    if ":" in text_value:
                        key, val = [normalize_space(part) for part in text_value.split(":", 1)]
                        if key and val:
                            attributes[key] = val
                    else:
                        attributes[f"attr_{len(attributes) + 1}"] = text_value

        source_updated_at = datetime.now(timezone.utc)
        hash_payload = {
            "sku": sku,
            "title": title,
            "brand": brand,
            "category": category,
            "price_amount": str(price_amount) if price_amount is not None else None,
            "currency": currency,
            "stock_status": stock_status,
            "promo_text": promo_text,
            "attributes": attributes,
            "source_url": canonical_url,
        }
        content_hash = compute_hash(hash_payload)
        provenance = {
            "listing_url": listing_context.get("listing_url") or "",
            "pdp_url": canonical_url,
            "retrieved_at": source_updated_at.isoformat(),
        }

        return ProductRecord(
            product_sku=sku[:64],
            listing_url=listing_context.get("listing_url"),
            pdp_url=canonical_url,
            source_url=canonical_url,
            title=title,
            brand=brand,
            category=category,
            price_amount=price_amount,
            currency=currency,
            stock_status=stock_status,
            promo_text=promo_text,
            attributes=attributes,
            source_updated_at=source_updated_at,
            fresh_until=self.fresh_until,
            content_hash=content_hash,
            provenance=provenance,
        )

    def crawl(self) -> List[ProductRecord]:
        records: List[ProductRecord] = []
        listing_urls = list(dict.fromkeys(self.args.listing_url or DEFAULT_LISTING_SEEDS))

        for listing_url in listing_urls:
            try:
                discovered = self.discover_listing_links(listing_url)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Listing crawl failed for %s: %s", listing_url, exc)
                continue

            if self.args.max_products:
                discovered = discovered[: self.args.max_products]

            for listing_context in discovered:
                if self.args.max_products and len(records) >= self.args.max_products:
                    break
                try:
                    product = self.parse_product(listing_context)
                    if product:
                        records.append(product)
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "PDP parse failed for %s: %s", listing_context.get("pdp_url"), exc
                    )
                    continue

        deduped: Dict[tuple, ProductRecord] = {}
        for record in records:
            key = (record.product_sku, record.content_hash)
            deduped[key] = record
        final_records = list(deduped.values())
        self.logger.info("Collected %s unique product states", len(final_records))
        return final_records

    def persist(self, records: List[ProductRecord]) -> None:
        snapshot_id = str(uuid.uuid4())
        crawl_started_at = self.now
        crawl_finished_at = datetime.now(timezone.utc)
        batch_hash = compute_hash(
            {
                "snapshot_at": self.now.isoformat(),
                "records": [r.content_hash for r in records],
            }
        )
        status = "dry_run" if self.args.dry_run else ("partial" if not records else "success")

        self.logger.info(
            "Snapshot %s status=%s records=%s dry_run=%s",
            snapshot_id,
            status,
            len(records),
            self.args.dry_run,
        )
        if self.args.dry_run:
            return

        if create_engine is None or text is None:
            raise RuntimeError(
                "sqlalchemy is required for database writes. Install dependencies from requirements.txt."
            )

        engine = create_engine(build_database_uri())
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO tecbite_catalog_snapshot (
                            snapshot_id, snapshot_at, crawl_started_at, crawl_finished_at,
                            status, source_host, batch_hash
                        ) VALUES (
                            :snapshot_id, :snapshot_at, :crawl_started_at, :crawl_finished_at,
                            :status, :source_host, :batch_hash
                        )
                        ON CONFLICT (batch_hash) DO UPDATE
                        SET snapshot_at = EXCLUDED.snapshot_at,
                            crawl_finished_at = EXCLUDED.crawl_finished_at,
                            status = EXCLUDED.status
                        """
                    ),
                    {
                        "snapshot_id": snapshot_id,
                        "snapshot_at": self.now,
                        "crawl_started_at": crawl_started_at,
                        "crawl_finished_at": crawl_finished_at,
                        "status": status,
                        "source_host": SOURCE_HOST,
                        "batch_hash": batch_hash,
                    },
                )

                for record in records:
                    conn.execute(
                        text(
                            """
                            INSERT INTO tecbite_product_state (
                                snapshot_id, product_sku, listing_url, pdp_url, source_url,
                                title, brand, category, price_amount, currency, stock_status,
                                promo_text, attributes, source_updated_at, fresh_until,
                                content_hash, provenance
                            ) VALUES (
                                :snapshot_id, :product_sku, :listing_url, :pdp_url, :source_url,
                                :title, :brand, :category, :price_amount, :currency, :stock_status,
                                :promo_text, CAST(:attributes AS jsonb), :source_updated_at, :fresh_until,
                                :content_hash, CAST(:provenance AS jsonb)
                            )
                            ON CONFLICT (snapshot_id, product_sku) DO UPDATE
                            SET listing_url = EXCLUDED.listing_url,
                                pdp_url = EXCLUDED.pdp_url,
                                source_url = EXCLUDED.source_url,
                                title = EXCLUDED.title,
                                brand = EXCLUDED.brand,
                                category = EXCLUDED.category,
                                price_amount = EXCLUDED.price_amount,
                                currency = EXCLUDED.currency,
                                stock_status = EXCLUDED.stock_status,
                                promo_text = EXCLUDED.promo_text,
                                attributes = EXCLUDED.attributes,
                                source_updated_at = EXCLUDED.source_updated_at,
                                fresh_until = EXCLUDED.fresh_until,
                                content_hash = EXCLUDED.content_hash,
                                provenance = EXCLUDED.provenance
                            """
                        ),
                        {
                            "snapshot_id": snapshot_id,
                            "product_sku": record.product_sku,
                            "listing_url": record.listing_url,
                            "pdp_url": record.pdp_url,
                            "source_url": record.source_url,
                            "title": record.title,
                            "brand": record.brand,
                            "category": record.category,
                            "price_amount": record.price_amount,
                            "currency": record.currency,
                            "stock_status": record.stock_status,
                            "promo_text": record.promo_text,
                            "attributes": json.dumps(record.attributes, ensure_ascii=True),
                            "source_updated_at": record.source_updated_at,
                            "fresh_until": record.fresh_until,
                            "content_hash": record.content_hash,
                            "provenance": json.dumps(record.provenance, ensure_ascii=True),
                        },
                    )
        except SQLAlchemyError as exc:
            self.logger.error("Database write failed: %s", exc)
            raise
        finally:
            engine.dispose()


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest Tecbite listing + PDP catalog snapshots into PostgreSQL.",
    )
    parser.add_argument(
        "--listing-url",
        action="append",
        help="Listing seed URL (repeat flag for multiple). Defaults to curated seeds.",
    )
    parser.add_argument(
        "--max-products",
        type=int,
        default=0,
        help="Limit total PDP pages parsed for safe runs (0 = no limit).",
    )
    parser.add_argument(
        "--freshness-minutes",
        type=int,
        default=DEFAULT_FRESHNESS_MINUTES,
        help="fresh_until offset from snapshot_at (minutes).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="HTTP retries per request.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl and parse without inserting into PostgreSQL.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    ingestor = TecbiteCatalogIngestor(args)
    try:
        records = ingestor.crawl()
        ingestor.persist(records)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("tecbite_catalog_etl").exception("ETL failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
