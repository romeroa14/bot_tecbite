#!/usr/bin/env python3
"""Deploy product-accuracy patches to n8n via Postgres (entity + history)."""
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
TOOL_WF = "C3Mx8TtH3ABEv178"

PREPARE_FITMENT_QUERY = (ROOT / "prepare_fitment_query.js").read_text()
FITMENT_LOOKUP_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f01"
PREPARE_FITMENT_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f02"

PATCHES: dict[str, dict[str, str]] = {
    AGENT_WF: {
        "Format Instagram Messages2": (ROOT / "format_instagram_messages_enforcer.js").read_text(),
        "Parse State Updates": (ROOT / "parse_state_updates_live.js").read_text(),
        "Roof Assets Config": (ROOT / "roof_assets_config_enforcer.js").read_text(),
        "Prepare Fitment Query": PREPARE_FITMENT_QUERY,
        "Build Instagram Request": (ROOT / "build_instagram_request.js").read_text(),
    },
    TOOL_WF: {
        "Format Response1": (ROOT / "tool_format_response_ranking.js").read_text(),
        "Format Response": (ROOT / "tool_format_response_ranking.js").read_text(),
    },
}
SYSTEM_PROMPT = (ROOT / "system_prompt.txt").read_text()


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


def psql_row(query: str) -> list[str]:
    line = psql(query).strip()
    if not line:
        return []
    # First column may be JSON text; split only on first tabs for multi-col rows
    return line.split("\t")


def psql_file(sql: str) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = PGPASSWORD
    subprocess.run(["psql", DB, "-v", "ON_ERROR_STOP=1"], input=sql, text=True, env=env, check=True)


def dollar_tag(payload: str) -> str:
    tag = "n8n_" + uuid.uuid4().hex
    while tag in payload:
        tag = "n8n_" + uuid.uuid4().hex
    return tag


def patch_nodes(nodes: list, mapping: dict[str, str]) -> tuple[list, list[str]]:
    changed: list[str] = []
    for node in nodes:
        name = node.get("name")
        if name in mapping:
            node.setdefault("parameters", {})["jsCode"] = mapping[name]
            changed.append(name)
        if name in {"AI Agent", "AI Agent2"}:
            options = node.setdefault("parameters", {}).setdefault("options", {})
            if options.get("systemMessage") != SYSTEM_PROMPT:
                options["systemMessage"] = SYSTEM_PROMPT
                changed.append(name)
    return nodes, changed


def ensure_fitment_lookup_chain(nodes: list, connections: dict) -> tuple[list, dict, list[str]]:
    """Insert Prepare Fitment Query + Fitment Lookup between AI Agent and Roof Assets Config."""
    changed: list[str] = []
    names = {n.get("name") for n in nodes}

    if "Prepare Fitment Query" not in names:
        nodes.append({
            "id": PREPARE_FITMENT_NODE_ID,
            "name": "Prepare Fitment Query",
            "type": "n8n-nodes-base.code",
            "typeVersion": 2,
            "position": [1160, 208],
            "parameters": {"jsCode": PREPARE_FITMENT_QUERY},
        })
        changed.append("Prepare Fitment Query (new node)")

    if "Fitment Lookup" not in names:
        nodes.append({
            "id": FITMENT_LOOKUP_NODE_ID,
            "name": "Fitment Lookup",
            "type": "n8n-nodes-base.executeWorkflow",
            "typeVersion": 1.2,
            "position": [1240, 208],
            "parameters": {
                "workflowId": {
                    "__rl": True,
                    "value": TOOL_WF,
                    "mode": "list",
                    "cachedResultName": "Tool - search_attributes_jsonb",
                },
                "workflowInputs": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "brand": "={{ $json.fitment_query ? $json.fitment_query.brand : '' }}",
                        "model": "={{ $json.fitment_query ? $json.fitment_query.model : '' }}",
                        "year": "={{ $json.fitment_query ? $json.fitment_query.year : 0 }}",
                        "roof_type": "={{ $json.fitment_query ? $json.fitment_query.roof_type : '' }}",
                    },
                },
                "options": {},
            },
        })
        changed.append("Fitment Lookup (new node)")

    agent_out = connections.get("AI Agent", {}).get("main", [[]])[0]
    targets = {c.get("node") for c in agent_out}
    desired_agent = [
        {"node": "Prepare Fitment Query", "type": "main", "index": 0},
        {"node": "Parse State Updates", "type": "main", "index": 0},
    ]
    if targets != {c["node"] for c in desired_agent}:
        connections["AI Agent"] = {"main": [desired_agent]}
        changed.append("connections: AI Agent")

    connections["Prepare Fitment Query"] = {
        "main": [[{"node": "Fitment Lookup", "type": "main", "index": 0}]],
    }
    connections["Fitment Lookup"] = {
        "main": [[{"node": "Roof Assets Config", "type": "main", "index": 0}]],
    }
    if "connections: fitment chain" not in changed:
        changed.append("connections: fitment chain")

    return nodes, connections, changed


def deploy_workflow(wf_id: str) -> None:
    version_id = psql(f"SELECT \"activeVersionId\" FROM workflow_entity WHERE id = '{wf_id}';").strip()
    nodes_text = psql(f"SELECT nodes::text FROM workflow_entity WHERE id = '{wf_id}';")
    conn_text = psql(f"SELECT connections::text FROM workflow_entity WHERE id = '{wf_id}';")
    name = psql(f"SELECT COALESCE(name,'') FROM workflow_entity WHERE id = '{wf_id}';").strip()
    description = psql(f"SELECT COALESCE(description,'') FROM workflow_entity WHERE id = '{wf_id}';").strip()
    authors = psql(
        f"SELECT COALESCE(authors,'deploy-script') FROM workflow_history WHERE \"versionId\" = '{version_id}';"
    ).strip() or "deploy-script"
    nodes = json.loads(nodes_text)
    connections = json.loads(conn_text)

    nodes, changed = patch_nodes(nodes, PATCHES.get(wf_id, {}))
    if wf_id == AGENT_WF:
        nodes, connections, chain_changed = ensure_fitment_lookup_chain(nodes, connections)
        changed = list(dict.fromkeys(changed + chain_changed))
    if not changed:
        print(f"{wf_id}: nothing to patch")
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
  '{wf_id}',
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
 WHERE id = '{wf_id}';

UPDATE workflow_entity SET active = false WHERE id = '{wf_id}';
UPDATE workflow_entity SET active = true WHERE id = '{wf_id}';
COMMIT;
"""
    psql_file(sql)
    print(f"{wf_id}: patched {', '.join(changed)} -> version {new_version}")


def main() -> None:
    deploy_workflow(TOOL_WF)
    deploy_workflow(AGENT_WF)
    print("Done.")


if __name__ == "__main__":
    main()
