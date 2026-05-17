-- ═════════════════════════════════════════════════════════════
-- 20260516_vendor_documents.sql
-- ─────────────────────────────────────────────────────────────
-- Unifica la ingesta documental por vendor (thule, weathertech,
-- curt, ...) en un set único de tablas con embeddings de 768
-- dimensiones (nomic-embed-text de Ollama).
--
-- Reemplaza el patrón `thule_document*` (vacío, sin uso) y crea
-- un esquema escalable a N marcas con índice HNSW para búsqueda
-- semántica eficiente.
-- ═════════════════════════════════════════════════════════════

BEGIN;

-- ── Extensiones requeridas ────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- para fuzzy match SKU↔doc

-- ── Drop tablas Thule legacy (vacías, confirmado) ────────────
DROP TABLE IF EXISTS thule_document_embedding CASCADE;
DROP TABLE IF EXISTS thule_document_chunk CASCADE;
DROP TABLE IF EXISTS thule_document CASCADE;

-- ═════════════════════════════════════════════════════════════
-- vendor_document — Una fila por URL crawleada
-- ═════════════════════════════════════════════════════════════
CREATE TABLE vendor_document (
    doc_id          UUID PRIMARY KEY,
    vendor          TEXT NOT NULL,                    -- 'thule' | 'weathertech' | 'curt' ...
    source_url      TEXT NOT NULL,
    source_host     TEXT NOT NULL,
    locale          TEXT NOT NULL DEFAULT 'es-PA',
    title           TEXT,
    category_hint   TEXT,                             -- derivado del crawler (ej. 'floorliner', 'portabicicletas')
    content_sha256  TEXT NOT NULL,
    etag            TEXT,
    last_modified   TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    status_code     INT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_vendor_document_vendor CHECK (vendor IN ('thule', 'weathertech', 'curt'))
);

CREATE UNIQUE INDEX uq_vendor_document_source_hash
  ON vendor_document (source_url, content_sha256);

CREATE INDEX idx_vendor_document_vendor_active
  ON vendor_document (vendor, is_active);

CREATE INDEX idx_vendor_document_category
  ON vendor_document (vendor, category_hint);

CREATE INDEX idx_vendor_document_fetched_at
  ON vendor_document (fetched_at DESC);

-- Trigram index sobre title para matching fuzzy con tecbite_product_state.title
CREATE INDEX idx_vendor_document_title_trgm
  ON vendor_document USING gin (title gin_trgm_ops);

-- ═════════════════════════════════════════════════════════════
-- vendor_document_chunk — Texto chunkeado para embeddings
-- ═════════════════════════════════════════════════════════════
CREATE TABLE vendor_document_chunk (
    chunk_id        BIGSERIAL PRIMARY KEY,
    doc_id          UUID NOT NULL REFERENCES vendor_document(doc_id) ON DELETE CASCADE,
    chunk_no        INT  NOT NULL,
    chunk_text      TEXT NOT NULL,
    token_count     INT  NOT NULL DEFAULT 0,
    chunk_sha256    TEXT NOT NULL UNIQUE,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_no)
);

CREATE INDEX idx_vendor_chunk_doc
  ON vendor_document_chunk (doc_id, chunk_no);

CREATE INDEX idx_vendor_chunk_metadata
  ON vendor_document_chunk USING gin (metadata);

-- ═════════════════════════════════════════════════════════════
-- vendor_document_embedding — vector(768) para nomic-embed-text
-- ═════════════════════════════════════════════════════════════
CREATE TABLE vendor_document_embedding (
    chunk_id        BIGINT PRIMARY KEY
                       REFERENCES vendor_document_chunk(chunk_id) ON DELETE CASCADE,
    embedding       vector(768) NOT NULL,
    embedding_model TEXT NOT NULL,                    -- 'nomic-embed-text', etc.
    embedded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_vendor_embedding_model
  ON vendor_document_embedding (embedding_model);

-- HNSW para búsqueda semántica rápida con similaridad coseno
CREATE INDEX idx_vendor_embedding_hnsw
  ON vendor_document_embedding USING hnsw (embedding vector_cosine_ops);

-- ═════════════════════════════════════════════════════════════
-- vendor_document_product_match — Vincula docs ↔ SKUs (paso 2 híbrido)
-- ═════════════════════════════════════════════════════════════
CREATE TABLE vendor_document_product_match (
    doc_id          UUID NOT NULL REFERENCES vendor_document(doc_id) ON DELETE CASCADE,
    product_sku     TEXT NOT NULL,                    -- referencia a tecbite_product_state.product_sku
    similarity      NUMERIC(5,4) NOT NULL,            -- 0.0000 .. 1.0000
    match_method    TEXT NOT NULL,                    -- 'trigram_title' | 'sku_in_url' | 'manual'
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (doc_id, product_sku),
    CONSTRAINT chk_vendor_match_method CHECK (
        match_method IN ('trigram_title', 'sku_in_url', 'manual', 'category_only')
    )
);

CREATE INDEX idx_vendor_match_sku
  ON vendor_document_product_match (product_sku);

CREATE INDEX idx_vendor_match_sim
  ON vendor_document_product_match (similarity DESC);

COMMIT;

-- ═════════════════════════════════════════════════════════════
-- POST-MIGRATION CHECKS
-- ═════════════════════════════════════════════════════════════
-- SELECT atttypmod AS embedding_dims FROM pg_attribute a
--   JOIN pg_class c ON a.attrelid = c.oid
--   WHERE c.relname = 'vendor_document_embedding' AND a.attname = 'embedding';
-- Esperado: 768
