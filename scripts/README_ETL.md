# ETL Execution Notes

This document covers the minimum local execution flow for fitment and catalog ETL runs used by the MVP Instagram backbone.

## Required environment variables

Define all database credentials before running scripts:

```bash
export DB_USER="<db_user>"
export DB_PASS="<db_password>"
export DB_HOST="<db_host>"
export DB_PORT="<db_port>"
export DB_NAME="<db_name>"
```

## 1) Fitment ETL (`etl.py`)

Run with SQL migrations and default curated Excel files:

```bash
python3 scripts/etl.py --run-migrations
```

Run with custom files:

```bash
python3 scripts/etl.py --excel-file "/path/file1.xlsx" --excel-file "/path/file2.xlsx"
```

Notes:
- Fails fast if DB env vars are missing.
- Emits `fitment_quality_report` and blocks load on critical data issues.
- Emits `fitment_precision_kpi` and flags an incident when precision is below 90%.

## 2) Catalog ETL (`tecbite_catalog_etl.py`)

Dry run:

```bash
python3 scripts/tecbite_catalog_etl.py --dry-run --max-products 20
```

Write snapshot:

```bash
python3 scripts/tecbite_catalog_etl.py --max-products 200
```

Notes:
- Fails fast if DB env vars are missing.
- Validates SKU format and dataset completeness before writing snapshot.
- If critical validation fails, no new snapshot is written and the previous valid snapshot remains active.
- Logs stale snapshot alerts when latest valid snapshot age is over 24 hours.

## 3) Thule docs ingest (`thule_docs_ingest.py`)

Dry run:

```bash
python3 scripts/thule_docs_ingest.py --dry-run --max-pages 10
```

Write chunks + embeddings:

```bash
python3 scripts/thule_docs_ingest.py --max-pages 30
```

Notes:
- Fails fast if DB env vars are missing (no hardcoded credential defaults).
- If `OPENAI_API_KEY` is not configured, ingest still runs but skips embeddings.
- Enforce this env var only when embeddings are required:

```bash
export OPENAI_API_KEY="..."
```

## 4) KPI diario Instagram-first (operacion)

Use la query consolidada del helper `instagram_daily_kpi_report` para validar objetivos MVP:

- slots completos >= 95%
- precision compatible >= 90%
- tecnicas sin fuente <= 5%
- latencia tecnica p95 <= 2500 ms

Consulta equivalente:

```sql
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
    COUNT(*) FILTER (WHERE event_type = 'recommendation' AND COALESCE(payload->>'source_ref', '') = '')::numeric AS recommendations_without_source,
    COUNT(*) FILTER (WHERE event_type = 'recommendation')::numeric AS recommendation_events,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY NULLIF(payload->>'technical_latency_ms', '')::double precision) AS technical_latency_p95_ms
  FROM instagram_conversation_event
  WHERE created_at >= NOW() - INTERVAL '1 day'
)
SELECT
  ROUND(CASE WHEN s.recommend_count = 0 THEN 0 ELSE (s.complete_slots::numeric / s.recommend_count::numeric) * 100 END, 2) AS slots_completion_percent,
  ROUND(CASE WHEN f.total_rows = 0 THEN 0 ELSE (f.compatible_rows / f.total_rows) * 100 END, 2) AS compatibility_precision_percent,
  ROUND(CASE WHEN e.recommendation_events = 0 THEN 0 ELSE (e.recommendations_without_source / e.recommendation_events) * 100 END, 2) AS technical_without_source_percent,
  ROUND(COALESCE(e.technical_latency_p95_ms, 0)::numeric, 2) AS technical_latency_p95_ms
FROM state_daily s
CROSS JOIN fitment_precision f
CROSS JOIN event_metrics e;
```
