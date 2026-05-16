"""Reusable SQL helpers for n8n PostgreSQL query nodes."""

SQL_UPSERT_INSTAGRAM_STATE = """
-- Upsert state by conversation_id with campaign-aware columns.
-- Params:
--   $1 => conversation_id
--   $2 => user_id
--   $3 => stage
--   $4 => make
--   $5 => model
--   $6 => year
--   $7 => category
--   $8 => slots_complete
--   $9 => last_message_id
--   $10 => campaign_id
--   $11 => ad_id
--   $12 => product_tag
INSERT INTO instagram_conversation_state (
    conversation_id,
    user_id,
    stage,
    make,
    model,
    year,
    category,
    slots_complete,
    last_message_id,
    campaign_id,
    ad_id,
    product_tag,
    updated_at
) VALUES (
    $1,
    $2,
    $3,
    NULLIF($4, ''),
    NULLIF($5, ''),
    $6::int,
    NULLIF($7, ''),
    COALESCE($8::boolean, FALSE),
    NULLIF($9, ''),
    NULLIF($10, ''),
    NULLIF($11, ''),
    NULLIF($12, ''),
    NOW()
)
ON CONFLICT (conversation_id) DO UPDATE
SET
    user_id = EXCLUDED.user_id,
    stage = EXCLUDED.stage,
    make = COALESCE(EXCLUDED.make, instagram_conversation_state.make),
    model = COALESCE(EXCLUDED.model, instagram_conversation_state.model),
    year = COALESCE(EXCLUDED.year, instagram_conversation_state.year),
    category = COALESCE(EXCLUDED.category, instagram_conversation_state.category),
    slots_complete = EXCLUDED.slots_complete,
    last_message_id = EXCLUDED.last_message_id,
    campaign_id = COALESCE(EXCLUDED.campaign_id, instagram_conversation_state.campaign_id),
    ad_id = COALESCE(EXCLUDED.ad_id, instagram_conversation_state.ad_id),
    product_tag = COALESCE(EXCLUDED.product_tag, instagram_conversation_state.product_tag),
    updated_at = NOW()
RETURNING *;
""".strip()

SQL_INSTAGRAM_IDEMPOTENCY_CHECK = """
-- Verify if a message_id was already processed for a conversation.
-- Params:
--   $1 => conversation_id
--   $2 => message_id
SELECT EXISTS (
    SELECT 1
    FROM instagram_conversation_event
    WHERE conversation_id = $1
      AND message_id = $2
) AS already_processed;
""".strip()

SQL_INSTAGRAM_STATE_BY_CONVERSATION = """
-- Load current conversational state for a conversation_id.
-- Params:
--   $1 => conversation_id
SELECT
    conversation_id,
    user_id,
    stage,
    make,
    model,
    year,
    category,
    slots_complete,
    last_message_id,
    updated_at
FROM instagram_conversation_state
WHERE conversation_id = $1
LIMIT 1;
""".strip()

SQL_INSTAGRAM_EVENT_REGISTER = """
-- Register conversational event idempotently by conversation+message+event_type.
-- Params:
--   $1 => conversation_id
--   $2 => message_id
--   $3 => event_type
--   $4 => payload JSON string
INSERT INTO instagram_conversation_event (
    conversation_id,
    message_id,
    event_type,
    payload
) VALUES (
    $1,
    $2,
    $3,
    COALESCE(NULLIF($4, '')::jsonb, '{}'::jsonb)
)
ON CONFLICT (conversation_id, message_id, event_type) DO NOTHING
RETURNING id;
""".strip()

SQL_FITMENT_LOOKUP = """
-- Canonical fitment lookup by make/model/year/category.
-- Params:
--   $1 => make
--   $2 => model
--   $3 => year
--   $4 => category
SELECT
    v.id AS vehicle_id,
    COALESCE(v.make, v.brand) AS make,
    v.model,
    $3::int AS year,
    COALESCE(v.category, v.type) AS category,
    vpf.product_sku AS sku
FROM vehicles v
JOIN vehicle_product_fitment vpf ON vpf.vehicle_id = v.id
WHERE LOWER(COALESCE(v.make, v.brand)) = LOWER($1)
  AND LOWER(v.model) = LOWER($2)
  AND $3::int BETWEEN v.year_start AND COALESCE(v.year_end, 9999)
  AND LOWER(COALESCE(v.category, v.type, '')) = LOWER($4)
  AND vpf.is_compatible = TRUE
ORDER BY v.id ASC
LIMIT 25;
""".strip()

SQL_LATEST_CATALOG_BY_SKU = """
-- Latest catalog state for a SKU.
-- Params:
--   $1 => product_sku
SELECT
    ps.product_sku,
    ps.title,
    ps.price_amount,
    ps.currency,
    ps.stock_status,
    ps.fresh_until,
    s.snapshot_id,
    s.snapshot_at,
    s.status
FROM tecbite_product_state ps
JOIN tecbite_catalog_snapshot s ON s.snapshot_id = ps.snapshot_id
WHERE LOWER(ps.product_sku) = LOWER($1)
  AND s.status IN ('success', 'partial')
ORDER BY s.snapshot_at DESC, ps.ingested_at DESC
LIMIT 1;
""".strip()

SQL_LATEST_TECBITE_COMMERCE_BY_REFERENCE = """
-- Latest Tecbite commerce state by SKU or product_reference.
-- Params:
--   $1 => product reference (sku or product_reference)
--   $2 => warning freshness window in minutes (e.g., 30)
--   $3 => hard stale window in minutes (e.g., 120)
WITH latest_commerce AS (
    SELECT
        ps.product_sku,
        ps.source_url,
        ps.pdp_url,
        ps.title,
        ps.price_amount,
        ps.currency,
        ps.stock_status,
        ps.promo_text,
        ps.fresh_until,
        ps.attributes,
        ps.provenance,
        s.snapshot_id,
        s.snapshot_at,
        EXTRACT(EPOCH FROM (NOW() - s.snapshot_at)) / 60.0 AS snapshot_age_minutes,
        CASE
            WHEN s.snapshot_at >= NOW() - ($2::int * INTERVAL '1 minute') THEN 'fresh'
            WHEN s.snapshot_at >= NOW() - ($3::int * INTERVAL '1 minute') THEN 'warning'
            ELSE 'stale'
        END AS freshness_state
    FROM tecbite_product_state ps
    JOIN tecbite_catalog_snapshot s ON s.snapshot_id = ps.snapshot_id
    WHERE
        LOWER(ps.product_sku) = LOWER($1)
        OR LOWER(COALESCE(ps.attributes->>'product_reference', '')) = LOWER($1)
    ORDER BY s.snapshot_at DESC
    LIMIT 1
)
SELECT *
FROM latest_commerce;
""".strip()

SQL_THULE_ES_PA_CHUNKS = """
-- Documentary chunks constrained to source=thule.com and locale=es-PA.
-- Params:
--   $1 => optional search token (sku/model/category). Pass NULL to skip text filter.
--   $2 => row limit (e.g., 8)
SELECT
    c.chunk_id,
    c.chunk_no,
    c.chunk_text,
    c.metadata,
    d.doc_id,
    d.source_url,
    d.locale,
    d.fetched_at
FROM thule_document_chunk c
JOIN thule_document d ON d.doc_id = c.doc_id
WHERE
    d.is_active = TRUE
    AND COALESCE(c.metadata->>'source', 'thule.com') = 'thule.com'
    AND COALESCE(c.metadata->>'locale', d.locale) = 'es-PA'
    AND (
        $1::text IS NULL
        OR c.chunk_text ILIKE '%' || $1 || '%'
        OR COALESCE(c.metadata->>'product_sku', '') ILIKE '%' || $1 || '%'
        OR COALESCE(c.metadata->>'category', '') ILIKE '%' || $1 || '%'
    )
ORDER BY d.fetched_at DESC, c.chunk_no ASC
LIMIT $2::int;
""".strip()

SQL_THULE_PGVECTOR_RETRIEVAL = """
-- Runtime technical retrieval using pgvector (primary path, no ILIKE-first).
-- Params:
--   $1 => embedding vector literal as text: "[0.1,0.2,...]"
--   $2 => minimum similarity threshold (0-1)
--   $3 => top-k row limit
SELECT
    c.chunk_id,
    c.chunk_no,
    LEFT(c.chunk_text, 1200) AS chunk_text,
    d.source_url,
    COALESCE(c.metadata->>'source_ref', d.source_url || '#chunk-' || c.chunk_no::text) AS source_ref,
    d.locale,
    e.embedding_model,
    (1 - (e.embedding <=> CAST($1 AS vector))) AS similarity_score
FROM thule_document_embedding e
JOIN thule_document_chunk c ON c.chunk_id = e.chunk_id
JOIN thule_document d ON d.doc_id = c.doc_id
WHERE d.is_active = TRUE
  AND COALESCE(c.metadata->>'source', 'thule.com') = 'thule.com'
  AND COALESCE(c.metadata->>'locale', d.locale) = 'es-PA'
  AND (1 - (e.embedding <=> CAST($1 AS vector))) >= $2::double precision
ORDER BY e.embedding <=> CAST($1 AS vector) ASC
LIMIT $3::int;
""".strip()

SQL_INSTAGRAM_CONVERSATION_MEMORY = """
-- Retrieve last 5 conversational events (inbound, recommendation, handoff)
-- for injection into LLM formatter prompt context.
-- Params:
--   $1 => conversation_id
SELECT
    event_type,
    payload->>'text' AS content,
    created_at
FROM instagram_conversation_event
WHERE conversation_id = $1
  AND event_type IN ('inbound', 'recommendation', 'handoff')
ORDER BY created_at DESC
LIMIT 5;
""".strip()

SQL_IMAGE_URL_LOOKUP = """
-- Resolve product image URL from the latest active catalog snapshot.
-- Params:
--   $1 => product_sku
SELECT
    ps.listing_url AS image_url
FROM tecbite_product_state ps
JOIN tecbite_catalog_snapshot s ON s.snapshot_id = ps.snapshot_id
WHERE LOWER(ps.product_sku) = LOWER($1)
  AND s.status IN ('success', 'partial')
ORDER BY s.snapshot_at DESC
LIMIT 1;
""".strip()

SQL_INSTAGRAM_DAILY_KPI_REPORT = """
-- Daily Instagram-first KPI rollup for MVP observability.
-- Includes slot completion, fitment precision, technical no-source ratio, and p95 technical latency.
WITH state_daily AS (
    SELECT
        COUNT(*) FILTER (WHERE slots_complete = TRUE) AS complete_slots,
        COUNT(*) FILTER (WHERE stage = 'recommend') AS recommend_count
    FROM instagram_conversation_state
    WHERE updated_at >= NOW() - INTERVAL '1 day'
),
fitment_precision AS (
    SELECT
        COUNT(*) FILTER (WHERE is_compatible = TRUE)::numeric AS compatible_rows,
        COUNT(*)::numeric AS total_rows
    FROM vehicle_product_fitment
),
event_metrics AS (
    SELECT
        COUNT(*) FILTER (
            WHERE event_type = 'recommendation'
              AND COALESCE(payload->>'source_ref', '') = ''
        )::numeric AS recommendations_without_source,
        COUNT(*) FILTER (WHERE event_type = 'recommendation')::numeric AS recommendation_events,
        percentile_cont(0.95) WITHIN GROUP (
            ORDER BY NULLIF(payload->>'technical_latency_ms', '')::double precision
        ) AS technical_latency_p95_ms
    FROM instagram_conversation_event
    WHERE created_at >= NOW() - INTERVAL '1 day'
)
SELECT
    ROUND(
        CASE
            WHEN s.recommend_count = 0 THEN 0
            ELSE (s.complete_slots::numeric / s.recommend_count::numeric) * 100
        END,
        2
    ) AS slots_completion_percent,
    ROUND(
        CASE
            WHEN f.total_rows = 0 THEN 0
            ELSE (f.compatible_rows / f.total_rows) * 100
        END,
        2
    ) AS compatibility_precision_percent,
    ROUND(
        CASE
            WHEN e.recommendation_events = 0 THEN 0
            ELSE (e.recommendations_without_source / e.recommendation_events) * 100
        END,
        2
    ) AS technical_without_source_percent,
    ROUND(COALESCE(e.technical_latency_p95_ms, 0)::numeric, 2) AS technical_latency_p95_ms
FROM state_daily s
CROSS JOIN fitment_precision f
CROSS JOIN event_metrics e;
""".strip()


def validate_credentials():
    """Validate required environment variables for Instagram agent activation.
    Returns (ok: bool, missing: list[str]).
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    required_vars = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
        'INSTAGRAM_ACCESS_TOKEN': os.getenv('INSTAGRAM_ACCESS_TOKEN', ''),
        'INSTAGRAM_VERIFY_TOKEN': os.getenv('INSTAGRAM_VERIFY_TOKEN', ''),
        'DB_PASS': os.getenv('DB_PASS', ''),
    }
    missing = [name for name, val in required_vars.items() if not val]
    return len(missing) == 0, missing


def get_sql_helper_queries():
    return {
        'upsert_state': SQL_UPSERT_INSTAGRAM_STATE,
        'state_by_conversation': SQL_INSTAGRAM_STATE_BY_CONVERSATION,
        'idempotency_check': SQL_INSTAGRAM_IDEMPOTENCY_CHECK,
        'register_event': SQL_INSTAGRAM_EVENT_REGISTER,
        'fitment_lookup': SQL_FITMENT_LOOKUP,
        'latest_catalog': SQL_LATEST_CATALOG_BY_SKU,
        'latest_tecbite_commerce_by_reference': SQL_LATEST_TECBITE_COMMERCE_BY_REFERENCE,
        'thule_pgvector_retrieval': SQL_THULE_PGVECTOR_RETRIEVAL,
        'thule_chunks_source_thule_com_locale_es_pa': SQL_THULE_ES_PA_CHUNKS,
        'instagram_daily_kpi_report': SQL_INSTAGRAM_DAILY_KPI_REPORT,
        'conversation_memory': SQL_INSTAGRAM_CONVERSATION_MEMORY,
        'image_url_lookup': SQL_IMAGE_URL_LOOKUP,
    }
