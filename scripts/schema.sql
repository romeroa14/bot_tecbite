CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Canonical fitment backbone (compatible with current ETL loads).
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(100) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100) NOT NULL,
    year_start INT NOT NULL,
    year_end INT DEFAULT 9999,
    type VARCHAR(100),
    category VARCHAR(100),
    roof_type VARCHAR(100),
    generation VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_vehicle_fitment_key
    ON vehicles (
        brand,
        model,
        year_start,
        COALESCE(year_end, 9999),
        COALESCE(generation, ''),
        COALESCE(roof_type, '')
    );

CREATE INDEX IF NOT EXISTS idx_vehicle_make_model_year_category
    ON vehicles (
        LOWER(COALESCE(make, brand)),
        LOWER(model),
        year_start,
        COALESCE(year_end, 9999),
        LOWER(COALESCE(category, type))
    );

CREATE TABLE IF NOT EXISTS products (
    sku VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(120),
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_category_sku
    ON products (LOWER(COALESCE(category, '')), sku);

CREATE TABLE IF NOT EXISTS fitment_kits (
    id BIGSERIAL PRIMARY KEY,
    vehicle_id INT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    foot_pack_sku VARCHAR(64),
    bar_front_sku VARCHAR(64),
    bar_rear_sku VARCHAR(64),
    kit_sku VARCHAR(64),
    max_load_kg NUMERIC(10, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fitment_kits_vehicle_front
    ON fitment_kits (
        vehicle_id,
        COALESCE(foot_pack_sku, ''),
        COALESCE(bar_front_sku, '')
    );

CREATE TABLE IF NOT EXISTS vehicle_product_fitment (
    vehicle_id INT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    product_sku VARCHAR(64) NOT NULL REFERENCES products(sku) ON DELETE CASCADE,
    is_compatible BOOLEAN NOT NULL DEFAULT TRUE,
    fitment_notes TEXT,
    pad_type VARCHAR(32),
    reinforcement_strap BOOLEAN,
    engineering_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (vehicle_id, product_sku)
);

CREATE INDEX IF NOT EXISTS idx_vpf_sku_vehicle
    ON vehicle_product_fitment (product_sku, vehicle_id);

-- Catalog dual-source snapshot backbone.
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

-- Instagram conversational state (idempotent event log + slot state).
CREATE TABLE IF NOT EXISTS instagram_conversation_state (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'instagram',
    stage TEXT NOT NULL,
    make TEXT,
    model TEXT,
    year INT,
    category TEXT,
    slots_complete BOOLEAN NOT NULL DEFAULT FALSE,
    last_message_id TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT instagram_conversation_state_stage_chk CHECK (
        stage IN (
            'ask_make',
            'ask_model',
            'ask_year',
            'ask_category',
            'collect_make',
            'collect_model',
            'collect_year',
            'collect_category',
            'recommend',
            'handoff'
        )
    )
);

CREATE TABLE IF NOT EXISTS instagram_conversation_event (
    id BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES instagram_conversation_state(conversation_id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT instagram_conversation_event_type_chk CHECK (
        event_type IN ('inbound', 'state_update', 'recommendation', 'handoff')
    ),
    UNIQUE (conversation_id, message_id, event_type)
);

CREATE INDEX IF NOT EXISTS idx_instagram_state_updated_at
    ON instagram_conversation_state (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_instagram_state_stage_slots
    ON instagram_conversation_state (stage, slots_complete);

CREATE INDEX IF NOT EXISTS idx_instagram_state_lookup
    ON instagram_conversation_state (
        LOWER(COALESCE(make, '')),
        LOWER(COALESCE(model, '')),
        year,
        LOWER(COALESCE(category, ''))
    );

CREATE INDEX IF NOT EXISTS idx_instagram_event_conv_msg
    ON instagram_conversation_event (conversation_id, message_id);

-- Technical docs + embeddings.
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
