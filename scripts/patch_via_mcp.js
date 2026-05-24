#!/usr/bin/env node
// Patch workflow via n8n MCP server
const http = require('http');

const REMOTE_URL = 'http://n8n.yavingos.com/mcp-server/http';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZTA4Njg3Yi1iYjkwLTQ5NDctYThlNy1jODI0YTg0MWY2ZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjBhNTNkMzQxLTU4MDktNDgyMS04Mjc2LTQzZDVkZGMxOGQ0NSIsImlhdCI6MTc3OTUxMDgwNX0.jlKApdN8OKb-jRFeJtRGKDx2FLBMPDpoFTNnsAZnXvQ';

function mcpCall(method, params, id) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({ jsonrpc: '2.0', method, params, id });
    const url = new URL(REMOTE_URL);
    const opts = {
      hostname: url.hostname, port: url.port || 80, path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const req = http.request(opts, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => {
        const lines = d.trim().split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { resolve(JSON.parse(line.substring(6))); return; } catch(_) {}
          } else if (line.startsWith('{')) {
            try { resolve(JSON.parse(line)); return; } catch(_) {}
          }
        }
        resolve(d);
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

async function main() {
  // Read the code from stdin
  const fs = require('fs');
  const code = fs.readFileSync('/var/www/html/tecbite/scripts/patch_sdk_final.js', 'utf8');
  
  console.log('Validating workflow code...');
  const valResult = await mcpCall('tools/call', {
    name: 'validate_workflow',
    arguments: { code }
  }, 1);
  
  const valText = valResult?.result?.content?.[0]?.text || JSON.stringify(valResult);
  console.log('Validation:', valText.substring(0, 300));
  
  if (valText.includes('"valid": true') || valText.includes('"valid":true')) {
    console.log('\nUpdating workflow...');
    const upResult = await mcpCall('tools/call', {
      name: 'update_workflow',
      arguments: {
        workflowId: 'oYVEXFvUFdCoe9VG',
        code,
        description: 'Instagram DM agent with merged quick_replies, 12-turn memory'
      }
    }, 2);
    const upText = upResult?.result?.content?.[0]?.text || JSON.stringify(upResult);
    console.log('Update:', upText.substring(0, 500));
    
    // Publish
    console.log('\nPublishing...');
    const pubResult = await mcpCall('tools/call', {
      name: 'publish_workflow',
      arguments: { workflowId: 'oYVEXFvUFdCoe9VG' }
    }, 3);
    const pubText = pubResult?.result?.content?.[0]?.text || JSON.stringify(pubResult);
    console.log('Publish:', pubText.substring(0, 300));
  } else {
    console.error('Validation failed!');
    process.exit(1);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
