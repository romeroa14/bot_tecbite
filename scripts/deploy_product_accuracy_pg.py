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
WT_WF = "RheRa72JDJql6QkU"

PREPARE_FITMENT_QUERY = (ROOT / "prepare_fitment_query.js").read_text()
FITMENT_LOOKUP_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f01"
PREPARE_FITMENT_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f02"
WT_LOOKUP_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f03"
CARGO_LOOKUP_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f04"
BIKE_LOOKUP_NODE_ID = "c8f4a2e1-6b3d-4f9a-9e2c-1d5a7b3c9f05"

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
    WT_WF: {
        "Normalize Input1": (ROOT / "tool_search_products_normalize.js").read_text(),
        "Format Response1": (ROOT / "tool_search_products_format.js").read_text(),
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
        if name in {"Query Products", "Query Products1"}:
            node.setdefault("parameters", {})["query"] = (
                "SELECT product_sku, title, brand, category,\n"
                "       price_amount, currency, stock_status, promo_text,\n"
                "       image_url\n"
                "  FROM tecbite_product_state,\n"
                "       (SELECT ($1::jsonb) AS j) AS params\n"
                " WHERE is_active = true\n"
                "   AND ((params.j->>'brand') = '' OR brand ILIKE '%' || (params.j->>'brand') || '%')\n"
                "   AND ((params.j->>'category') = '' OR category ILIKE '%' || (params.j->>'category') || '%')\n"
                "   AND ((params.j->>'vehicle_make') = '' OR title ILIKE '%' || (params.j->>'vehicle_make') || '%')\n"
                "   AND ((params.j->>'vehicle_model') = '' OR title ILIKE '%' || (params.j->>'vehicle_model') || '%')\n"
                " ORDER BY CASE stock_status WHEN 'in_stock' THEN 1 WHEN 'out_of_stock' THEN 2 ELSE 3 END,\n"
                "          price_amount ASC NULLS LAST\n"
                " LIMIT 100;"
            )
            opts = node.setdefault("parameters", {}).setdefault("options", {})
            opts["queryReplacement"] = (
                "={{ JSON.stringify({ brand: $json.brand, category: $json.category, limit: Number($json.limit) || 10, "
                "vehicle_make: $json.vehicle_make || '', vehicle_model: $json.vehicle_model || '', vehicle_year: $json.vehicle_year || null }) }}"
            )
            changed.append("Query Products SQL")
        if name == "Fitment Lookup":
            wi = node.setdefault("parameters", {}).setdefault("workflowInputs", {}).setdefault("value", {})
            wi["brand"] = "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.brand : '' }}"
            wi["model"] = "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.model : '' }}"
            wi["year"] = "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.year : 0 }}"
            wi["roof_type"] = "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.roof_type : '' }}"
            changed.append("Fitment Lookup inputs")
        if name == "WT Product Lookup":
            wi = node.setdefault("parameters", {}).setdefault("workflowInputs", {}).setdefault("value", {})
            wi["brand"] = "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.brand : '' }}"
            wi["category"] = "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.category : '' }}"
            wi["limit"] = "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.limit : 0 }}"
            wi["vehicle_make"] = "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.make : '' }}"
            wi["vehicle_model"] = "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.model : '' }}"
            wi["vehicle_year"] = "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.year : 0 }}"
            changed.append("WT Product Lookup inputs")
        if name == "Thule Cargo Lookup":
            wi = node.setdefault("parameters", {}).setdefault("workflowInputs", {}).setdefault("value", {})
            wi["brand"] = "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.brand : '' }}"
            wi["category"] = "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.category : '' }}"
            wi["limit"] = "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.limit : 0 }}"
            wi["cargo_type"] = "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.cargo_type : '' }}"
            changed.append("Thule Cargo Lookup inputs")
        if name == "Thule Bike Lookup":
            wi = node.setdefault("parameters", {}).setdefault("workflowInputs", {}).setdefault("value", {})
            wi["brand"] = "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.brand : '' }}"
            wi["category"] = "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.category : '' }}"
            wi["limit"] = "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.limit : 0 }}"
            wi["thule_mount"] = "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.thule_mount : '' }}"
            wi["thule_bike_type"] = "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.thule_bike_type : '' }}"
            changed.append("Thule Bike Lookup inputs")
        if name == "Save Lead State":
            q = node.setdefault("parameters", {}).get("query", "")
            if "product_tag" not in q:
                node["parameters"]["query"] = q.replace(
                    "  last_message_id,\n  updated_at\n) VALUES (",
                    "  last_message_id,\n  product_tag,\n  updated_at\n) VALUES (",
                ).replace(
                    "  $9,\n  NOW()\n)",
                    "  $9,\n  NULLIF($14, 'null'),\n  NOW()\n)",
                ).replace(
                    "  last_message_id = EXCLUDED.last_message_id,\n  updated_at = NOW();",
                    "  last_message_id = EXCLUDED.last_message_id,\n  product_tag = COALESCE(EXCLUDED.product_tag, instagram_conversation_state.product_tag),\n  updated_at = NOW();",
                )
                opts = node.setdefault("parameters", {}).setdefault("options", {})
                opts["queryReplacement"] = (
                    "={{ [$json.conversation_id, $json.user_id, $json.stage, $json.make, $json.model, "
                    "$json.year, $json.category, $json.slots_complete, $json.message_id, "
                    "JSON.stringify($json.inbound_payload), JSON.stringify($json.outbound_payload), "
                    "$json.roof_type, $json.reset_vehicle_context, $json.product_tag] }}"
                )
                changed.append("Save Lead State product_tag")
        if name == "Get Lead State":
            q = node.setdefault("parameters", {}).get("query", "")
            if "s.product_tag" not in q or "s.roof_type" not in q:
                node["parameters"]["query"] = (
                    "SELECT \n"
                    "  COALESCE(s.conversation_id, $1) as conversation_id,\n"
                    "  COALESCE(s.user_id, $1) as user_id,\n"
                    "  COALESCE(s.channel, 'instagram') as channel,\n"
                    "  COALESCE(s.stage, 'greeting') as stage,\n"
                    "  s.make,\n"
                    "  s.model,\n"
                    "  s.year,\n"
                    "  s.category,\n"
                    "  s.roof_type,\n"
                    "  s.product_tag,\n"
                    "  COALESCE(s.slots_complete, false) as slots_complete,\n"
                    "  s.last_message_id\n"
                    "FROM (SELECT $1 AS dummy_id) d\n"
                    "LEFT JOIN instagram_conversation_state s ON s.conversation_id = d.dummy_id;"
                )
                changed.append("Get Lead State product_tag+roof_type")
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
                        "brand": "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.brand : '' }}",
                        "model": "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.model : '' }}",
                        "year": "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.year : 0 }}",
                        "roof_type": "={{ $('Prepare Fitment Query').item.json.fitment_query ? $('Prepare Fitment Query').item.json.fitment_query.roof_type : '' }}",
                    },
                },
                "options": {},
            },
        })
        changed.append("Fitment Lookup (new node)")

    if "WT Product Lookup" not in names:
        nodes.append({
            "id": WT_LOOKUP_NODE_ID,
            "name": "WT Product Lookup",
            "type": "n8n-nodes-base.executeWorkflow",
            "typeVersion": 1.2,
            "position": [1320, 208],
            "parameters": {
                "workflowId": {
                    "__rl": True,
                    "value": WT_WF,
                    "mode": "list",
                    "cachedResultName": "Tool - search_products_by_brand",
                },
                "workflowInputs": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "brand": "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.brand : '' }}",
                        "category": "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.category : '' }}",
                        "limit": "={{ $('Prepare Fitment Query').item.json.wt_query ? $('Prepare Fitment Query').item.json.wt_query.limit : 0 }}",
                        "vehicle_make": "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.make : '' }}",
                        "vehicle_model": "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.model : '' }}",
                        "vehicle_year": "={{ $('Prepare Fitment Query').item.json.wt_query && $('Prepare Fitment Query').item.json.wt_query.vehicle ? $('Prepare Fitment Query').item.json.wt_query.vehicle.year : 0 }}",
                    },
                },
                "options": {},
            },
        })
        changed.append("WT Product Lookup (new node)")

    if "Thule Cargo Lookup" not in names:
        nodes.append({
            "id": CARGO_LOOKUP_NODE_ID,
            "name": "Thule Cargo Lookup",
            "type": "n8n-nodes-base.executeWorkflow",
            "typeVersion": 1.2,
            "position": [1400, 208],
            "parameters": {
                "workflowId": {
                    "__rl": True,
                    "value": WT_WF,
                    "mode": "list",
                    "cachedResultName": "Tool - search_products_by_brand",
                },
                "workflowInputs": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "brand": "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.brand : '' }}",
                        "category": "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.category : '' }}",
                        "limit": "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.limit : 0 }}",
                        "cargo_type": "={{ $('Prepare Fitment Query').item.json.cargo_query ? $('Prepare Fitment Query').item.json.cargo_query.cargo_type : '' }}",
                    },
                },
                "options": {},
            },
        })
        changed.append("Thule Cargo Lookup (new node)")

    if "Thule Bike Lookup" not in names:
        nodes.append({
            "id": BIKE_LOOKUP_NODE_ID,
            "name": "Thule Bike Lookup",
            "type": "n8n-nodes-base.executeWorkflow",
            "typeVersion": 1.2,
            "position": [1480, 208],
            "parameters": {
                "workflowId": {
                    "__rl": True,
                    "value": WT_WF,
                    "mode": "list",
                    "cachedResultName": "Tool - search_products_by_brand",
                },
                "workflowInputs": {
                    "mappingMode": "defineBelow",
                    "value": {
                        "brand": "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.brand : '' }}",
                        "category": "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.category : '' }}",
                        "limit": "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.limit : 0 }}",
                        "thule_mount": "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.thule_mount : '' }}",
                        "thule_bike_type": "={{ $('Prepare Fitment Query').item.json.bike_query ? $('Prepare Fitment Query').item.json.bike_query.thule_bike_type : '' }}",
                    },
                },
                "options": {},
            },
        })
        changed.append("Thule Bike Lookup (new node)")

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
        "main": [[{"node": "WT Product Lookup", "type": "main", "index": 0}]],
    }
    connections["WT Product Lookup"] = {
        "main": [[{"node": "Thule Cargo Lookup", "type": "main", "index": 0}]],
    }
    connections["Thule Cargo Lookup"] = {
        "main": [[{"node": "Thule Bike Lookup", "type": "main", "index": 0}]],
    }
    connections["Thule Bike Lookup"] = {
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
    deploy_workflow(WT_WF)
    deploy_workflow(AGENT_WF)
    print("Done.")


if __name__ == "__main__":
    main()
