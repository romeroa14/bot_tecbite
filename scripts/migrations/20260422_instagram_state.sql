BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Fitment backbone (compatible with current ETL tables)
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    brand VARCHAR(100) NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100) NOT NULL,
    year_start INT NOT NULL,
    year_end INT,
    type VARCHAR(100),
    category VARCHAR(100),
    roof_type VARCHAR(100),
    generation VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE vehicles
    ALTER COLUMN year_end SET DEFAULT 9999;

UPDATE vehicles
SET
    make = COALESCE(NULLIF(make, ''), brand),
    category = COALESCE(NULLIF(category, ''), type)
WHERE make IS NULL OR category IS NULL OR make = '' OR category = '';

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

-- Conversational state for Instagram workflow
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

COMMIT;
