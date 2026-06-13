#!/usr/bin/env python3
"""Telegram ops migration only.

The Notify Telegram Ops node was removed from the Instagram agent workflow
(oYVEXFvUFdCoe9VG). Ops alerts will move to a separate Odoo workflow.

To remove the node again if re-added: python3 scripts/remove_telegram_ops.py
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

DB = "postgresql://postgres@n8n.yavingos.com:5433/n8ntecbite_db"
PGPASSWORD = "Tecbite20$"
ROOT = Path(__file__).resolve().parent
AGENT_WF = "oYVEXFvUFdCoe9VG"
NOTIFY_NODE_ID = "d4e8f1a2-9b3c-4d5e-8f7a-6b5c4d3e2f01"
NOTIFY_CODE = (ROOT / "telegram_ops_notify.js").read_text()
MIGRATION = (ROOT / "migrations" / "20260612_telegram_ops.sql").read_text()


def psql(query: str) -> str:
    env = os.environ.copy()
    env["PGPASSWORD"] = PGPASSWORD
    return subprocess.run(
        ["psql", DB, "-t", "-A", "-c", query],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    ).stdout


def psql_file(sql: str) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = PGPASSWORD
    subprocess.run(["psql", DB, "-v", "ON_ERROR_STOP=1"], input=sql, text=True, env=env, check=True)


def dollar_tag(payload: str) -> str:
    tag = "n8n_" + uuid.uuid4().hex
    while tag in payload:
        tag = "n8n_" + uuid.uuid4().hex
    return tag


def deploy_migration() -> None:
    psql_file(MIGRATION)
    print("Migration 20260612_telegram_ops applied")


def deploy_notify_node() -> None:
    version_id = psql(f'SELECT "activeVersionId" FROM workflow_entity WHERE id = \'{AGENT_WF}\';').strip()
    nodes = json.loads(psql(f"SELECT nodes::text FROM workflow_entity WHERE id = '{AGENT_WF}';"))
    connections = json.loads(psql(f"SELECT connections::text FROM workflow_entity WHERE id = '{AGENT_WF}';"))
    name = psql(f"SELECT COALESCE(name,'') FROM workflow_entity WHERE id = '{AGENT_WF}';").strip()
    description = psql(f"SELECT COALESCE(description,'') FROM workflow_entity WHERE id = '{AGENT_WF}';").strip()
    authors = psql(
        f'SELECT COALESCE(authors,\'deploy-script\') FROM workflow_history WHERE "versionId" = \'{version_id}\';'
    ).strip() or "deploy-script"

    names = {n.get("name") for n in nodes}
    changed = []

    if "Notify Telegram Ops" not in names:
        nodes.append({
            "id": NOTIFY_NODE_ID,
            "name": "Notify Telegram Ops",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1320, 432],
            "parameters": {"jsCode": NOTIFY_CODE, "mode": "runOnceForAllItems"},
        })
        changed.append("Notify Telegram Ops (new)")

    for node in nodes:
        if node.get("name") == "Notify Telegram Ops":
            node.setdefault("parameters", {})["jsCode"] = NOTIFY_CODE
            node["parameters"]["mode"] = "runOnceForAllItems"
            changed.append("Notify Telegram Ops code")

    connections["Save Lead State"] = {
        "main": [[{"node": "Notify Telegram Ops", "type": "main", "index": 0}]],
    }
    changed.append("connections Save Lead State -> Notify")

    if not changed:
        print("Notify node already up to date")
        return

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    conn_json = json.dumps(connections, ensure_ascii=False)
    new_version = str(uuid.uuid4())
    nodes_tag = dollar_tag(nodes_json)
    conn_tag = dollar_tag(conn_json)
    name_tag = dollar_tag(name)
    desc_tag = dollar_tag(description)
    authors_tag = dollar_tag(authors)

    sql = f"""
BEGIN;
INSERT INTO workflow_history ("versionId", "workflowId", authors, nodes, connections, name, description, "createdAt", "updatedAt")
VALUES (
  '{new_version}',
  '{AGENT_WF}',
  ${authors_tag}${authors}${authors_tag}$,
  ${nodes_tag}${nodes_json}${nodes_tag}$::json,
  ${conn_tag}${conn_json}${conn_tag}$::json,
  ${name_tag}${name}${name_tag}$,
  ${desc_tag}${description}${desc_tag}$,
  NOW(),
  NOW()
)
ON CONFLICT ("versionId") DO UPDATE
   SET nodes = EXCLUDED.nodes,
       connections = EXCLUDED.connections,
       "updatedAt" = NOW();

UPDATE workflow_entity
   SET nodes = ${nodes_tag}${nodes_json}${nodes_tag}$::json,
       connections = ${conn_tag}${conn_json}${conn_tag}$::json,
       "activeVersionId" = '{new_version}',
       "updatedAt" = NOW()
 WHERE id = '{AGENT_WF}';

UPDATE workflow_entity SET active = false WHERE id = '{AGENT_WF}';
UPDATE workflow_entity SET active = true WHERE id = '{AGENT_WF}';
COMMIT;
"""
    psql_file(sql)
    print(f"Agent workflow patched: {', '.join(changed)} -> {new_version}")


def main() -> None:
    deploy_migration()
    print("Notify node NOT deployed (removed from fitment workflow; use remove_telegram_ops.py if needed)")


if __name__ == "__main__":
    main()
