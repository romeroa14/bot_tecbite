#!/usr/bin/env node
/**
 * Patch product accuracy: ranking in search_attributes_jsonb + enforcer in Format Instagram Messages2
 */
const fs = require('fs');
const http = require('http');
const path = require('path');

const BASE = 'http://n8n.yavingos.com';
const TOKEN = process.env.N8N_API_TOKEN || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZTA4Njg3Yi1iYjkwLTQ5NDctYThlNy1jODI0YTg0MWY2ZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjBhNTNkMzQxLTU4MDktNDgyMS04Mjc2LTQzZDVkZGMxOGQ0NSIsImlhdCI6MTc3OTUxMDgwNX0.jlKApdN8OKb-jRFeJtRGKDx2FLBMPDpoFTNnsAZnXvQ';
const AGENT_WF = 'oYVEXFvUFdCoe9VG';
const TOOL_WF = 'C3Mx8TtH3ABEv178';

const ROOT = path.join(__dirname, '..');
const FORMAT_RANKING = fs.readFileSync(path.join(__dirname, 'tool_format_response_ranking.js'), 'utf8');
const FORMAT_IG = fs.readFileSync(path.join(__dirname, 'format_instagram_messages_enforcer.js'), 'utf8');

const PROMPT_ADDITION = `

## PRECISIÓN DE PRODUCTO — BARRAS (CRÍTICO)
Cuando search_attributes_jsonb devuelva found=true:
- Recomienda UN SOLO kit: results[0] o primary_recommendation. NUNCA cites otros kits de results[1+].
- En la primera respuesta tras elegir techo (QR:ROOF_A..E): SOLO kit + disponibilidad. NO listes barras ni precios de barras.
- Las barras SOLO si el usuario pide fotos/detalle/precios de barras, y SOLO desde bars[] del tool.
- PROHIBIDO mencionar SKU, precio o modelo Thule que no aparezca literalmente en results[0] o bars[].
- El formatter construye el mensaje final; tu respuesta puede ser breve. No inventes WingBar, Evo, Edge ni precios extra.`;

function apiCall(method, apiPath, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(apiPath, BASE);
    const payload = body ? JSON.stringify(body) : null;
    const opts = {
      hostname: url.hostname,
      port: url.port || 80,
      path: url.pathname,
      method,
      headers: {
        Authorization: `Bearer ${TOKEN}`,
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
    };
    if (payload) opts.headers['Content-Length'] = Buffer.byteLength(payload);
    const req = http.request(opts, (res) => {
      let d = '';
      res.on('data', (c) => { d += c; });
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch { resolve(d); }
      });
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function patchWorkflow(id, name, mutator) {
  console.log(`\nFetching ${name} (${id})...`);
  const wf = await apiCall('GET', `/api/v1/workflows/${id}`);
  if (!wf.nodes) throw new Error(`Failed to fetch ${id}: ${JSON.stringify(wf).slice(0, 200)}`);
  const changed = mutator(wf);
  if (!changed) {
    console.log(`  No changes for ${name}`);
    return;
  }
  const result = await apiCall('PUT', `/api/v1/workflows/${id}`, {
    name: wf.name,
    nodes: wf.nodes,
    connections: wf.connections,
    settings: wf.settings,
  });
  console.log(`  Saved: ${result.id || 'ok'}`);
  const pub = await apiCall('POST', `/api/v1/workflows/${id}/activate`);
  console.log(`  Active: ${pub.active !== false}`);
}

async function main() {
  await patchWorkflow(TOOL_WF, 'Tool search_attributes_jsonb', (wf) => {
    let changed = false;
    for (const node of wf.nodes) {
      if (node.name === 'Format Response' || node.name === 'Format Response1') {
        node.parameters.jsCode = FORMAT_RANKING;
        changed = true;
        console.log(`  ✅ ${node.name}: ranking patch`);
      }
    }
    return changed;
  });

  await patchWorkflow(AGENT_WF, 'Instagram Agent', (wf) => {
    let changed = false;
    const ROOF_ENFORCER = fs.readFileSync(path.join(__dirname, 'roof_assets_config_enforcer.js'), 'utf8');
    for (const node of wf.nodes) {
      if (node.name === 'Format Instagram Messages2') {
        node.parameters.jsCode = FORMAT_IG;
        changed = true;
        console.log('  ✅ Format Instagram Messages2: enforcer patch');
      }
      if (node.name === 'Roof Assets Config') {
        node.parameters.jsCode = ROOF_ENFORCER;
        changed = true;
        console.log('  ✅ Roof Assets Config: enforcer patch');
      }
      if (node.name === 'AI Agent2' || node.name === 'AI Agent') {
        const opts = node.parameters?.options;
        const sm = opts?.systemMessage || node.parameters?.systemMessage || '';
        if (!sm.includes('PRECISIÓN DE PRODUCTO — BARRAS')) {
          if (opts) opts.systemMessage = sm + PROMPT_ADDITION;
          else node.parameters.systemMessage = sm + PROMPT_ADDITION;
          changed = true;
          console.log('  ✅ AI Agent: prompt accuracy rules');
        }
      }
    }
    return changed;
  });

  const toolJsonPath = path.join(ROOT, 'n8n/tools/tool_search_attributes_jsonb.json');
  const toolJson = JSON.parse(fs.readFileSync(toolJsonPath, 'utf8'));
  for (const node of toolJson.nodes) {
    if (node.name === 'Format Response') {
      node.parameters.jsCode = FORMAT_RANKING;
    }
  }
  fs.writeFileSync(toolJsonPath, JSON.stringify(toolJson, null, 2) + '\n');
  console.log('\n✅ Local tool_search_attributes_jsonb.json updated');
  console.log('\nDone.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
