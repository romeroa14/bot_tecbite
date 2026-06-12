#!/usr/bin/env python3
"""Fix Instagram Send2 Graph URL and page access token in n8n workflow."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
import urllib.request

DB = "postgresql://postgres@n8n.yavingos.com:5433/n8ntecbite_db"
PGPASSWORD = "Tecbite20$"
WF_ID = "oYVEXFvUFdCoe9VG"
SEND_NODE = "Instagram Send2"
GRAPH_VERSION = "v21.0"


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


def resolve_page_token(user_token: str) -> tuple[str, str]:
    url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts"
        f"?fields=id,name,access_token,instagram_business_account&access_token={user_token}"
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    pages = data.get("data") or []
    if not pages:
        raise RuntimeError("No pages returned for this user token")
    page = pages[0]
    page_id = str(page["id"])
    page_token = str(page["access_token"])
    ig_id = str((page.get("instagram_business_account") or {}).get("id") or "")
    return page_id, page_token, ig_id


def patch_send_node(nodes: list, page_id: str, page_token: str) -> bool:
    changed = False
    for node in nodes:
        if node.get("name") != SEND_NODE:
            continue
        params = node.setdefault("parameters", {})
        correct_url = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/messages"
        if params.get("url") != correct_url:
            params["url"] = correct_url
            changed = True
        qparams = params.setdefault("queryParameters", {}).setdefault("parameters", [])
        if not qparams:
            qparams.append({"name": "access_token", "value": page_token})
            changed = True
        else:
            for item in qparams:
                if item.get("name") == "access_token" and item.get("value") != page_token:
                    item["value"] = page_token
                    changed = True
        break
    return changed


def deploy(nodes: list, connections: list, wf_id: str) -> None:
    version_id = psql(f'SELECT "activeVersionId" FROM workflow_entity WHERE id = \'{wf_id}\';').strip()
    name = psql(f"SELECT COALESCE(name,'') FROM workflow_entity WHERE id = '{wf_id}';").strip()
    description = psql(f"SELECT COALESCE(description,'') FROM workflow_entity WHERE id = '{wf_id}';").strip()
    authors = psql(
        f"SELECT COALESCE(authors,'deploy-script') FROM workflow_history WHERE \"versionId\" = '{version_id}';"
    ).strip() or "deploy-script"

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
);

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
    print(f"Patched {SEND_NODE} -> version {new_version}")


def main() -> None:
    nodes = json.loads(psql(f"SELECT nodes::text FROM workflow_entity WHERE id = '{WF_ID}';"))
    connections = json.loads(psql(f"SELECT connections::text FROM workflow_entity WHERE id = '{WF_ID}';"))

    send = next(n for n in nodes if n.get("name") == SEND_NODE)
    user_token = send["parameters"]["queryParameters"]["parameters"][0]["value"]

    page_id, page_token, ig_id = resolve_page_token(user_token)
    print(f"Resolved page_id={page_id} ig_id={ig_id}")

    if not patch_send_node(nodes, page_id, page_token):
        print("No changes needed")
        return

    deploy(nodes, connections, WF_ID)
    print("Done.")


if __name__ == "__main__":
    main()
