"""Reusable SQL helpers for n8n PostgreSQL query nodes."""

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


def get_sql_helper_queries():
    return {
        'latest_tecbite_commerce_by_reference': SQL_LATEST_TECBITE_COMMERCE_BY_REFERENCE,
        'thule_chunks_source_thule_com_locale_es_pa': SQL_THULE_ES_PA_CHUNKS,
    }
