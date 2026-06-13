#!/usr/bin/env python3
"""Remove Notify Telegram Ops node from Instagram agent workflow."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

DB = "postgresql://postgres@n8n.yavingos.com:5433/n8ntecbite_db"
PGPASSWORD = "Tecbite20$"
AGENT_WF = "oYVEXFvUFdCoe9VG"
NOTIFY_NODE_ID = "d4e8f1a2-9b3c-4d5e-8f7a-6b5c4d3e2f01"


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


def remove_notify_node() -> None:
    version_id = psql(f'SELECT "activeVersionId" FROM workflow_entity WHERE id = \'{AGENT_WF}\';').strip()
    nodes = json.loads(psql(f"SELECT nodes::text FROM workflow_entity WHERE id = '{AGENT_WF}';"))
    connections = json.loads(psql(f"SELECT connections::text FROM workflow_entity WHERE id = '{AGENT_WF}';"))
    name = psql(f"SELECT COALESCE(name,'') FROM workflow_entity WHERE id = '{AGENT_WF}';").strip()
    description = psql(f"SELECT COALESCE(description,'') FROM workflow_entity WHERE id = '{AGENT_WF}';").strip()
    authors = psql(
        f'SELECT COALESCE(authors,\'deploy-script\') FROM workflow_history WHERE "versionId" = \'{version_id}\';'
    ).strip() or "deploy-script"

    before = len(nodes)
    nodes = [
        n for n in nodes
        if n.get("name") != "Notify Telegram Ops" and n.get("id") != NOTIFY_NODE_ID
    ]
    removed_nodes = before - len(nodes)

    if "Save Lead State" in connections:
        del connections["Save Lead State"]

    if "Notify Telegram Ops" in connections:
        del connections["Notify Telegram Ops"]

    if removed_nodes == 0 and "Save Lead State" not in connections:
        print("Notify Telegram Ops already removed")
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
    print(f"Removed Notify Telegram Ops ({removed_nodes} node(s)); workflow -> {new_version}")


if __name__ == "__main__":
    remove_notify_node()
