from __future__ import annotations

import json
from typing import Any

import psycopg2
import psycopg2.extras


def connect(dsn: str):
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_all(conn, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def fetch_one(conn, sql: str, params: tuple | None = None) -> dict[str, Any] | None:
    rows = fetch_all(conn, sql, params)
    return rows[0] if rows else None


def try_log_notification(
    conn,
    conversation_id: str,
    message_id: str,
    notify_type: str,
    payload: dict,
) -> bool:
    """Return True if logged (first time), False if duplicate."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO telegram_ops_notification (conversation_id, message_id, notify_type, payload)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (conversation_id, message_id, notify_type) DO NOTHING
            RETURNING id
            """,
            (conversation_id, message_id or "", notify_type, json.dumps(payload)),
        )
        row = cur.fetchone()
        conn.commit()
        return row is not None


SQL_TODAY_SUMMARY = """
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE slots_complete) AS ready,
  COUNT(*) FILTER (WHERE stage = 'handoff') AS handoffs,
  COUNT(*) FILTER (WHERE category ILIKE '%%barras%%') AS barras,
  COUNT(*) FILTER (WHERE category ILIKE '%%alfomb%%') AS alfombras
FROM instagram_conversation_state
WHERE updated_at >= date_trunc('day', NOW() AT TIME ZONE 'America/Panama')
"""

SQL_ACTIVE = """
SELECT conversation_id, make, model, year, category, stage, roof_type, slots_complete, updated_at
FROM instagram_conversation_state
WHERE updated_at >= NOW() - INTERVAL '6 hours'
ORDER BY updated_at DESC
LIMIT 15
"""

SQL_HANDOFFS = """
SELECT s.conversation_id, s.make, s.model, s.year, s.category, s.stage, s.updated_at,
       e.payload->>'text' AS last_outbound
FROM instagram_conversation_state s
LEFT JOIN LATERAL (
  SELECT payload FROM instagram_conversation_event ev
  WHERE ev.conversation_id = s.conversation_id
  ORDER BY ev.created_at DESC LIMIT 1
) e ON TRUE
WHERE s.stage = 'handoff' OR s.updated_at >= NOW() - INTERVAL '24 hours' AND s.stage = 'handoff'
ORDER BY s.updated_at DESC
LIMIT 10
"""

SQL_CLIENT = """
SELECT s.*,
  (
    SELECT json_agg(json_build_object(
      'event_type', e.event_type,
      'text', COALESCE(e.payload->>'text', ''),
      'at', e.created_at
    ) ORDER BY e.created_at DESC)
    FROM (
      SELECT event_type, payload, created_at
      FROM instagram_conversation_event
      WHERE conversation_id = s.conversation_id
      ORDER BY created_at DESC
      LIMIT 8
    ) e
  ) AS events
FROM instagram_conversation_state s
WHERE s.conversation_id = %s OR s.user_id = %s
LIMIT 1
"""

SQL_SEARCH_CLIENTS = """
SELECT conversation_id, make, model, year, category, stage, updated_at
FROM instagram_conversation_state
WHERE conversation_id ILIKE %s
   OR user_id ILIKE %s
   OR (make ILIKE %s AND model ILIKE %s)
ORDER BY updated_at DESC
LIMIT 8
"""
