import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError
except Exception:  # noqa: BLE001
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]

    class SQLAlchemyError(Exception):
        """Fallback SQLAlchemy error type when dependency is missing."""

VENDOR = "thule"
SEED_URLS = (
    "https://www.thule.com/es-pa/bike-rack",
    "https://www.thule.com/es-pa/cargo-carrier",
    "https://www.thule.com/es-pa/roof-rack",
    "https://www.thule.com/es-pa/luggage",
    "https://www.thule.com/es-pa/water-sport",
    "https://www.thule.com/es-pa/child-bike-seats",
    "https://www.thule.com/es-pa/strollers",
)
ALLOWED_HOST = "www.thule.com"
ALLOWED_PATH_PREFIX = "/es-pa/"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = (2, 8, 20)
DEFAULT_MAX_PAGES = 200
DEFAULT_CHUNK_WORDS = 180
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_LOCALE = "es-PA"

# Heuristic para inferir category_hint del path de la URL
CATEGORY_HINTS = {
    "bike-rack": "bike-rack",
    "roof-rack": "roof-rack",
    "cargo-carrier": "cargo-carrier",
    "car-top-carrier": "cargo-carrier",
    "luggage": "luggage",
    "sport-rack": "sport-rack",
    "water-sport": "water-sport",
    "child-bike-seats": "child-bike-seats",
    "strollers": "strollers",
    "about-thule": "about",
    "careers": "about",
    "sustainability": "about",
    "warranty": "about",
    "activities": "activities",
    "articles": "articles",
}
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 ThuleDocsIngest/1.0"
)
REQUIRED_DB_ENV = ("DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME")

CONTENT_SELECTORS = (
    "main",
    "article",
    "[role='main']",
    ".rich-text",
    ".content",
    ".product-description",
    ".product-specifications",
    ".article-content",
    ".techspec",
)
REMOVABLE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "header",
    "footer",
    "nav",
    ".breadcrumb",
    ".filter",
    ".sorting",
    ".geo-location",
    ".country-selector",
    ".language-selector",
)


@dataclass
class DocumentChunk:
    chunk_no: int
    chunk_text: str
    token_count: int
    chunk_sha256: str
    metadata: Dict[str, str]


@dataclass
class DocumentRecord:
    doc_id: str
    source_url: str
    locale: str
    title: Optional[str]
    content_sha256: str
    etag: Optional[str]
    last_modified: Optional[str]
    fetched_at: datetime
    status_code: int
    text_content: str
    chunks: List[DocumentChunk]


def build_database_uri() -> str:
    missing = [name for name in REQUIRED_DB_ENV if not os.getenv(name)]
    if missing:
        raise EnvironmentError(
            "Missing DB environment variables: "
            + ", ".join(missing)
            + ". Configure them before running docs ingest."
        )
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    return f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def sha256_text(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def token_estimate(text_value: str) -> int:
    return max(1, len(text_value.split()))


def calculate_information_density(text_value: str) -> float:
    """
    Calcula densidad de información como ratio de palabras únicas vs total.
    Valores bajos indican contenido repetitivo o de baja calidad.
    """
    words = text_value.lower().split()
    if not words:
        return 0.0
    unique_words = set(words)
    return len(unique_words) / len(words)


def is_low_quality_chunk(chunk_text: str) -> bool:
    """
    Filtra chunks de baja calidad:
    - Menos de 30 tokens
    - Densidad de información < 0.3 (muy repetitivo)
    - Contiene principalmente palabras de navegación
    """
    if len(chunk_text.strip()) < 50:
        return True
    
    word_count = len(chunk_text.split())
    if word_count < 30:
        return True
    
    density = calculate_information_density(chunk_text)
    if density < 0.3:
        return True
    
    # Palabras de navegación comunes que indican ruido
    nav_keywords = ['filtro', 'ordenar', 'precio', 'destacado', 'nuevo', 'mayor', 'menor', 'seleccionar', 'país', 'región', 'venezuela', 'spanish', 'close', 'filter', 'show', 'hide', 'collapse', 'expand']
    nav_count = sum(1 for word in chunk_text.lower().split() if word in nav_keywords)
    if nav_count > word_count * 0.3:  # Más del 30% son palabras de navegación
        return True
    
    return False


def chunk_text_blocks(text_value: str, chunk_words: int) -> List[str]:
    """
    Chunking inteligente por delimitadores semánticos (párrafos, secciones)
    en lugar de palabras fijas. Prioriza párrafos completos y respeta límites de tokens.
    """
    if not text_value:
        return []
    
    # Dividir por párrafos primero (doble salto de línea)
    paragraphs = [p.strip() for p in text_value.split('\n\n') if p.strip()]
    
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_word_count = 0
    
    for para in paragraphs:
        para_words = para.split()
        para_word_count = len(para_words)
        
        # Si el párrafo es muy largo (> chunk_words), dividirlo por oraciones
        if para_word_count > chunk_words:
            sentences = [s.strip() for s in para.split('.') if s.strip()]
            for sent in sentences:
                sent_words = sent.split()
                sent_word_count = len(sent_words)
                
                # Si agregar esta oración excede el límite, guardar chunk actual
                if current_word_count + sent_word_count > chunk_words and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = []
                    current_word_count = 0
                
                if sent_words:
                    current_chunk.append(sent)
                    current_word_count += sent_word_count
        else:
            # Si agregar este párrafo excede el límite, guardar chunk actual
            if current_word_count + para_word_count > chunk_words and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            
            if para_words:
                current_chunk.append(para)
                current_word_count += para_word_count
    
    # Agregar el último chunk si tiene contenido
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def is_allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != ALLOWED_HOST:
        return False
    return parsed.path.startswith(ALLOWED_PATH_PREFIX)


def vector_literal(values: List[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def infer_category_hint(url: str) -> Optional[str]:
    path = urlparse(url).path.lower()
    for keyword, hint in CATEGORY_HINTS.items():
        if keyword in path:
            return hint
    return None


class ThuleDocsIngestor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.logger = logging.getLogger("thule_docs_ingest")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.ollama_url = args.ollama_url.rstrip("/")
        self.embeddings_enabled = self._ping_ollama()

    def _ping_ollama(self) -> bool:
        if self.args.skip_embeddings:
            self.logger.info("--skip-embeddings set; embeddings disabled.")
            return False
        try:
            r = self.session.get(f"{self.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                self.logger.info("Ollama OK at %s", self.ollama_url)
                return True
            self.logger.warning("Ollama responded %s; embeddings disabled", r.status_code)
            return False
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "Ollama unreachable at %s (%s); chunks will be ingested WITHOUT embeddings.",
                self.ollama_url, exc,
            )
            return False

    def fetch(self, url: str) -> requests.Response:
        last_error: Optional[Exception] = None
        for attempt in range(self.args.retries):
            try:
                response = self.session.get(url, timeout=self.args.timeout)
                if 500 <= response.status_code < 600:
                    raise requests.HTTPError(
                        f"{response.status_code} from {url}", response=response
                    )
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait_seconds = DEFAULT_BACKOFF_SECONDS[min(attempt, len(DEFAULT_BACKOFF_SECONDS) - 1)]
                self.logger.warning(
                    "Fetch failed (%s/%s) %s: %s; retry in %ss",
                    attempt + 1,
                    self.args.retries,
                    url,
                    exc,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
        assert last_error is not None
        raise last_error

    def extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links: Set[str] = set()
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            if not href:
                continue
            absolute = urljoin(base_url, href)
            if "#" in absolute:
                absolute = absolute.split("#", 1)[0]
            if is_allowed_url(absolute):
                links.add(absolute.rstrip("/"))
        return sorted(links)

    def extract_text(self, soup: BeautifulSoup) -> str:
        for selector in REMOVABLE_SELECTORS:
            for node in soup.select(selector):
                node.decompose()

        text_blocks: List[str] = []
        for selector in CONTENT_SELECTORS:
            node = soup.select_one(selector)
            if not node:
                continue
            block = normalize_space(node.get_text(" ", strip=True))
            if len(block) >= 120:
                text_blocks.append(block)

        if not text_blocks:
            body = soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)
            normalized = normalize_space(body)
            if normalized:
                text_blocks.append(normalized)

        unique: List[str] = []
        seen: Set[str] = set()
        for block in text_blocks:
            digest = sha256_text(block)
            if digest in seen:
                continue
            seen.add(digest)
            unique.append(block)
        return "\n\n".join(unique)

    def crawl(self) -> List[DocumentRecord]:
        queue: List[str] = [url.rstrip("/") for url in (self.args.seed_url or SEED_URLS)]
        visited: Set[str] = set()
        documents: List[DocumentRecord] = []

        while queue and len(visited) < self.args.max_pages:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            try:
                response = self.fetch(current)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed to fetch %s: %s", current, exc)
                continue

            if response.status_code >= 400:
                self.logger.warning("Skipping %s with status %s", current, response.status_code)
                continue

            soup = BeautifulSoup(response.text, "lxml")
            links = self.extract_links(soup, response.url)
            for link in links:
                if link not in visited and link not in queue and len(visited) + len(queue) < self.args.max_pages:
                    queue.append(link)

            text_content = self.extract_text(soup)
            if len(text_content) < 200:
                continue

            title_node = soup.select_one("title")
            title = normalize_space(title_node.get_text(" ", strip=True)) if title_node else None
            content_sha = sha256_text(text_content)
            chunks = self.build_chunks(current, text_content)
            doc = DocumentRecord(
                doc_id=str(uuid.uuid4()),
                source_url=response.url,
                locale=DEFAULT_LOCALE,
                title=title,
                content_sha256=content_sha,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                fetched_at=datetime.now(timezone.utc),
                status_code=response.status_code,
                text_content=text_content,
                chunks=chunks,
            )
            doc.category_hint = infer_category_hint(response.url)
            documents.append(doc)
            self.logger.info(
                "Captured %s [%s] (%s chunks)", response.url, doc.category_hint or "-", len(chunks)
            )
        return documents

    def build_chunks(self, source_url: str, text_content: str) -> List[DocumentChunk]:
        chunk_texts = chunk_text_blocks(text_content, self.args.chunk_words)
        chunks: List[DocumentChunk] = []
        filtered_count = 0
        for idx, chunk in enumerate(chunk_texts, start=1):
            # Filtrar chunks de baja calidad
            if is_low_quality_chunk(chunk):
                filtered_count += 1
                self.logger.debug("Filtered low-quality chunk %s from %s", idx, source_url)
                continue
            
            metadata = {
                "vendor": VENDOR,
                "source": "thule.com",
                "locale": DEFAULT_LOCALE,
                "source_url": source_url,
                "source_ref": f"{source_url}#chunk-{idx}",
                "category_hint": infer_category_hint(source_url) or "",
            }
            chunks.append(
                DocumentChunk(
                    chunk_no=idx,
                    chunk_text=chunk,
                    token_count=token_estimate(chunk),
                    chunk_sha256=sha256_text(chunk),
                    metadata=metadata,
                )
            )
        if filtered_count > 0:
            self.logger.info("Filtered %s low-quality chunks from %s", filtered_count, source_url)
        return chunks

    def embed_text(self, text_value: str) -> Optional[List[float]]:
        if not self.embeddings_enabled:
            return None
        try:
            r = self.session.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.args.embedding_model, "prompt": text_value},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            embedding = data.get("embedding")
            if not embedding or len(embedding) != 768:
                self.logger.warning(
                    "Unexpected embedding from Ollama (len=%s); skipping",
                    len(embedding) if embedding else 0,
                )
                return None
            return embedding
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Ollama embedding failed; skipping chunk: %s", exc)
            return None

    def persist(self, documents: List[DocumentRecord]) -> None:
        self.logger.info(
            "Prepared %s documents and %s chunks (dry_run=%s)",
            len(documents),
            sum(len(doc.chunks) for doc in documents),
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
                for doc in documents:
                    source_host = urlparse(doc.source_url).netloc
                    category_hint = getattr(doc, "category_hint", None) or infer_category_hint(doc.source_url)
                    conn.execute(
                        text(
                            """
                            INSERT INTO vendor_document (
                                doc_id, vendor, source_url, source_host, locale, title, category_hint,
                                content_sha256, etag, last_modified, fetched_at, status_code, is_active
                            ) VALUES (
                                :doc_id, :vendor, :source_url, :source_host, :locale, :title, :category_hint,
                                :content_sha256, :etag, :last_modified, :fetched_at, :status_code, TRUE
                            )
                            ON CONFLICT (source_url, content_sha256) DO UPDATE
                            SET fetched_at = EXCLUDED.fetched_at,
                                status_code = EXCLUDED.status_code,
                                category_hint = EXCLUDED.category_hint,
                                is_active = TRUE
                            """
                        ),
                        {
                            "doc_id": doc.doc_id,
                            "vendor": VENDOR,
                            "source_url": doc.source_url,
                            "source_host": source_host,
                            "locale": doc.locale,
                            "title": doc.title,
                            "category_hint": category_hint,
                            "content_sha256": doc.content_sha256,
                            "etag": doc.etag,
                            "last_modified": doc.last_modified,
                            "fetched_at": doc.fetched_at,
                            "status_code": doc.status_code,
                        },
                    )

                    for chunk in doc.chunks:
                        inserted_chunk = conn.execute(
                            text(
                                """
                                INSERT INTO vendor_document_chunk (
                                    doc_id, chunk_no, chunk_text, token_count, chunk_sha256, metadata
                                ) VALUES (
                                    :doc_id, :chunk_no, :chunk_text, :token_count, :chunk_sha256, CAST(:metadata AS jsonb)
                                )
                                ON CONFLICT (chunk_sha256) DO UPDATE
                                SET chunk_text = EXCLUDED.chunk_text,
                                    token_count = EXCLUDED.token_count,
                                    metadata = EXCLUDED.metadata
                                RETURNING chunk_id
                                """
                            ),
                            {
                                "doc_id": doc.doc_id,
                                "chunk_no": chunk.chunk_no,
                                "chunk_text": chunk.chunk_text,
                                "token_count": chunk.token_count,
                                "chunk_sha256": chunk.chunk_sha256,
                                "metadata": json.dumps(chunk.metadata, ensure_ascii=True),
                            },
                        ).scalar_one()

                        embedding = self.embed_text(chunk.chunk_text)
                        if embedding is None:
                            continue
                        conn.execute(
                            text(
                                """
                                INSERT INTO vendor_document_embedding (
                                    chunk_id, embedding, embedding_model, embedded_at
                                ) VALUES (
                                    :chunk_id, CAST(:embedding_literal AS vector), :embedding_model, :embedded_at
                                )
                                ON CONFLICT (chunk_id) DO UPDATE
                                SET embedding = EXCLUDED.embedding,
                                    embedding_model = EXCLUDED.embedding_model,
                                    embedded_at = EXCLUDED.embedded_at
                                """
                            ),
                            {
                                "chunk_id": inserted_chunk,
                                "embedding_literal": vector_literal(embedding),
                                "embedding_model": self.args.embedding_model,
                                "embedded_at": datetime.now(timezone.utc),
                            },
                        )
        except SQLAlchemyError as exc:
            self.logger.error("Database write failed: %s", exc)
            raise
        finally:
            engine.dispose()


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl Thule es-PA documentation pages and ingest chunked content to PostgreSQL/PGVector."
    )
    parser.add_argument(
        "--seed-url",
        action="append",
        help="Seed URL under https://www.thule.com/es-pa/ (repeat flag for multiple).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Maximum number of same-domain pages to crawl.",
    )
    parser.add_argument(
        "--chunk-words",
        type=int,
        default=DEFAULT_CHUNK_WORDS,
        help="Chunk size measured in words.",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="Ollama embedding model (default: nomic-embed-text, 768 dims).",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Ollama base URL (default: http://n8n.yavingos.com:11434).",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Ingest chunks WITHOUT embeddings (back-fill later).",
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
        help="Retries per request.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl and transform only; skip database writes.",
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
    ingestor = ThuleDocsIngestor(args)
    try:
        documents = ingestor.crawl()
        ingestor.persist(documents)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("thule_docs_ingest").exception("Ingest failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
