BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS tecbite_catalog_snapshot (
    snapshot_id UUID PRIMARY KEY,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    crawl_started_at TIMESTAMPTZ,
    crawl_finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'success',
    error_summary TEXT,
    source_host TEXT NOT NULL DEFAULT 'www.tecbite.com',
    batch_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tecbite_catalog_snapshot_status_chk CHECK (
        status IN ('success', 'partial', 'failed', 'dry_run')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tecbite_catalog_snapshot_batch_hash
    ON tecbite_catalog_snapshot (batch_hash);
CREATE INDEX IF NOT EXISTS idx_tecbite_catalog_snapshot_snapshot_at
    ON tecbite_catalog_snapshot (snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_tecbite_catalog_snapshot_status
    ON tecbite_catalog_snapshot (status);

CREATE TABLE IF NOT EXISTS tecbite_product_state (
    snapshot_id UUID NOT NULL REFERENCES tecbite_catalog_snapshot (snapshot_id) ON DELETE CASCADE,
    product_sku TEXT NOT NULL,
    listing_url TEXT,
    pdp_url TEXT,
    source_url TEXT NOT NULL,
    title TEXT,
    brand TEXT,
    category TEXT,
    price_amount NUMERIC(12, 2),
    currency TEXT NOT NULL DEFAULT 'USD',
    stock_status TEXT,
    promo_text TEXT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at TIMESTAMPTZ,
    fresh_until TIMESTAMPTZ,
    content_hash TEXT NOT NULL,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_id, product_sku)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tecbite_product_state_hash
    ON tecbite_product_state (product_sku, content_hash);
CREATE INDEX IF NOT EXISTS idx_tecbite_product_state_snapshot_desc
    ON tecbite_product_state (product_sku, snapshot_id DESC);
CREATE INDEX IF NOT EXISTS idx_tecbite_product_state_stock
    ON tecbite_product_state (stock_status);
CREATE INDEX IF NOT EXISTS idx_tecbite_product_state_fresh_until
    ON tecbite_product_state (fresh_until);
CREATE INDEX IF NOT EXISTS idx_tecbite_product_state_attributes
    ON tecbite_product_state USING GIN (attributes);

CREATE TABLE IF NOT EXISTS thule_document (
    doc_id UUID PRIMARY KEY,
    source_url TEXT NOT NULL,
    locale TEXT NOT NULL DEFAULT 'es-PA',
    source_host TEXT NOT NULL DEFAULT 'www.thule.com',
    title TEXT,
    content_sha256 TEXT NOT NULL,
    etag TEXT,
    last_modified TEXT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status_code INTEGER,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_thule_document_source_hash
    ON thule_document (source_url, content_sha256);
CREATE INDEX IF NOT EXISTS idx_thule_document_locale_active
    ON thule_document (locale, is_active);
CREATE INDEX IF NOT EXISTS idx_thule_document_fetched_at
    ON thule_document (fetched_at DESC);

CREATE TABLE IF NOT EXISTS thule_document_chunk (
    chunk_id BIGSERIAL PRIMARY KEY,
    doc_id UUID NOT NULL REFERENCES thule_document (doc_id) ON DELETE CASCADE,
    chunk_no INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    chunk_sha256 TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, chunk_no),
    UNIQUE (chunk_sha256)
);

CREATE INDEX IF NOT EXISTS idx_thule_document_chunk_doc
    ON thule_document_chunk (doc_id, chunk_no);
CREATE INDEX IF NOT EXISTS idx_thule_document_chunk_metadata
    ON thule_document_chunk USING GIN (metadata);

CREATE TABLE IF NOT EXISTS thule_document_embedding (
    chunk_id BIGINT PRIMARY KEY REFERENCES thule_document_chunk (chunk_id) ON DELETE CASCADE,
    embedding VECTOR(1536) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thule_document_embedding_model
    ON thule_document_embedding (embedding_model);
CREATE INDEX IF NOT EXISTS idx_thule_document_embedding_hnsw
    ON thule_document_embedding USING hnsw (embedding vector_cosine_ops);

COMMIT;
