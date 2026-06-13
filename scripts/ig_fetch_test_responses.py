#!/usr/bin/env python3
"""Fetch Instagram bot responses from Postgres for test conversation IDs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"


def load_env() -> None:
    if not ENV.exists():
        return
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def fetch(conversation_ids: list[str]) -> None:
    load_env()
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "n8n.yavingos.com"),
        port=int(os.environ.get("DB_PORT", "5433")),
        dbname=os.environ.get("DB_NAME", "n8ntecbite_db"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASS", os.environ.get("PGPASSWORD", "")),
    )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for cid in conversation_ids:
                print("\n" + "=" * 72)
                print(f"CONVERSATION: {cid}")
                print("=" * 72)

                cur.execute(
                    """
                    SELECT category, make, model, year, stage, product_tag, roof_type, updated_at
                      FROM instagram_conversation_state
                     WHERE conversation_id = %s
                    """,
                    (cid,),
                )
                state = cur.fetchone()
                if state:
                    print("STATE:", json.dumps(dict(state), default=str, ensure_ascii=False))
                else:
                    print("STATE: (none)")

                cur.execute(
                    """
                    SELECT event_type, message_id,
                           payload->>'text' AS text,
                           payload->'inbound'->>'text' AS inbound_text,
                           created_at
                      FROM instagram_conversation_event
                     WHERE conversation_id = %s
                     ORDER BY created_at ASC, id ASC
                    """,
                    (cid,),
                )
                rows = cur.fetchall()
                if not rows:
                    print("EVENTS: (none)")
                    continue
                for i, row in enumerate(rows, 1):
                    et = row["event_type"]
                    txt = (row.get("text") or row.get("inbound_text") or "").strip()
                    preview = txt.replace("\n", " | ")[:200]
                    print(f"  [{i}] {row['created_at']} {et}: {preview}")
                    if et == "recommendation" and txt:
                        print("  --- full outbound ---")
                        print(txt)
                        print("  --- end ---")
    finally:
        conn.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: ig_fetch_test_responses.py <conversation_id> [...]", file=sys.stderr)
        return 1
    fetch(sys.argv[1:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
