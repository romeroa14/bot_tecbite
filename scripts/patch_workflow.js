#!/usr/bin/env node
// Patch specific nodes in the Tecbite AI Agent workflow
const http = require('http');

const BASE = 'http://n8n.yavingos.com';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ZTA4Njg3Yi1iYjkwLTQ5NDctYThlNy1jODI0YTg0MWY2ZTMiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6IjBhNTNkMzQxLTU4MDktNDgyMS04Mjc2LTQzZDVkZGMxOGQ0NSIsImlhdCI6MTc3OTUxMDgwNX0.jlKApdN8OKb-jRFeJtRGKDx2FLBMPDpoFTNnsAZnXvQ';
const WF_ID = 'oYVEXFvUFdCoe9VG';

function apiCall(method, path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE);
    const payload = body ? JSON.stringify(body) : null;
    const opts = {
      hostname: url.hostname, port: url.port || 80, path: url.pathname,
      method, headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      }
    };
    if (payload) opts.headers['Content-Length'] = Buffer.byteLength(payload);
    const req = http.request(opts, res => {
      let d = ''; res.on('data', c => d += c); res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch(e) { resolve(d); }
      });
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function main() {
  // 1. Get current workflow
  console.log('Fetching workflow...');
  const wf = await apiCall('GET', `/api/v1/workflows/${WF_ID}`);
  if (!wf.nodes) { console.error('Failed to fetch workflow', wf); process.exit(1); }
  
  let changed = false;
  
  for (const node of wf.nodes) {
    // Fix 1: Increase Window Memory from 6 to 12
    if (node.name === 'Window Memory2') {
      node.parameters.contextWindowLength = 12;
      changed = true;
      console.log('✅ Window Memory: 6 → 12 turns');
    }
    
    // Fix 2: Update Format Instagram Messages2 - merge text+quick_replies into single item
    if (node.name === 'Format Instagram Messages2') {
      node.parameters.jsCode = FORMAT_MESSAGES_CODE;
      changed = true;
      console.log('✅ Format Instagram Messages2: patched');
    }
    
    // Fix 3: Update Build Instagram Request - handle merged format
    if (node.name === 'Build Instagram Request') {
      node.parameters.jsCode = BUILD_REQUEST_CODE;
      changed = true;
      console.log('✅ Build Instagram Request: patched');
    }
  }
  
  if (!changed) { console.error('No nodes found to patch!'); process.exit(1); }
  
  // 2. Save
  console.log('Saving workflow...');
  const result = await apiCall('PATCH', `/api/v1/workflows/${WF_ID}`, {
    nodes: wf.nodes,
    connections: wf.connections,
    settings: wf.settings
  });
  console.log('Result:', result.id ? `✅ Updated ${result.id}` : JSON.stringify(result).substring(0, 200));
  
  // 3. Publish
  console.log('Publishing...');
  const pub = await apiCall('POST', `/api/v1/workflows/${WF_ID}/activate`);
  console.log('Published:', pub.active ? '✅ Active' : JSON.stringify(pub).substring(0, 200));
}

// ============= PATCHED CODE =============

const FORMAT_MESSAGES_CODE = `// Format Instagram Messages — merge text + quick_replies into single message
const agentOutput = $input.first().json;
const outputText = agentOutput.output || agentOutput.text || '';

let user_id = '';
let inboundText = '';
try { user_id = $('Filter & Normalize2').item.json.user_id || ''; } catch (_) {}
try { inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim(); } catch (_) {}

const fold = (v) => String(v||'').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
const outbound = fold(outputText);
const inboundFold = fold(inboundText.replace(/^qr:/i, ''));

// --- Menu detection ---
const explicitRoof = outputText.includes('[ROOF_MENU]');
const explicitMain = outputText.includes('[MAIN_MENU]');
const explicitWt = outputText.includes('[WT_MENU]');

const roofProductCtx = /\\b(barras?|roof\\s*racks?|portaequipajes?|portabici|canasta|ba[uú]l)\\b/i.test(outputText + ' ' + inboundFold);
const wtProductCtx = /\\b(alfombras?|floor\\s*liners?|cargo\\s+liners?|weathertech)\\b/i.test(outputText + ' ' + inboundFold);
const roofCue = /\\btipo\\s+de\\s+techo\\b/i.test(outputText) || /\\bOpci[oó]n\\s+[A-E]\\b/i.test(outputText);
const wtCue = /\\b(fila|filas|universal|FloorLiner)\\b/i.test(outputText) && /\\b(tipo|cu[aá]l)\\b/i.test(outputText);
const mainCue = /\\b(qu[eé]|que)\\s+(deseas|tipo)\\b/i.test(outbound) || (
  [/barras?/i, /portabic/i, /alfombras?/i, /canasta|ba[uú]l/i].filter(r => r.test(outputText)).length >= 2
);

const askingVehicle = /\\b(marca|modelo|año)\\b/i.test(outputText) && /\\b(cu[aá]l|indic|dime|necesito)\\b/i.test(outbound);

let roofMenu = explicitRoof || (!explicitWt && !explicitMain && roofProductCtx && roofCue && !askingVehicle);
let wtMenu = explicitWt || (!explicitRoof && !explicitMain && wtProductCtx && wtCue && !askingVehicle);
let mainMenu = explicitMain || (!explicitRoof && !explicitWt && mainCue && !askingVehicle);

// Priority: roof > wt > main
if (roofMenu && wtMenu) wtMenu = false;
if (roofMenu && mainMenu) mainMenu = false;
if (wtMenu && mainMenu) mainMenu = false;

const hasMenu = roofMenu || wtMenu || mainMenu;

// --- Roof images ---
const ROOF_IMAGES = {
  MENU: 'https://drive.google.com/uc?export=view&id=1ett4opof8jzK9APUJtF71kXnEBwYYs-4',
  ROOF_A: 'https://drive.google.com/uc?export=view&id=1f7d0gXJ-PLWxUQ-yRxjlqRlAogqToDOR',
  ROOF_B: 'https://drive.google.com/uc?export=view&id=15KVOsDgmM9DQw1vSDxY7bIuXaBl7i_WK',
  ROOF_C: 'https://drive.google.com/uc?export=view&id=1cFLKfJeqTKIx1hiC6lUFQzBCWyfUopp6',
  ROOF_D: 'https://drive.google.com/uc?export=view&id=1vbRJIfryNZr0TEPzrvml9LWhJ0k0DGMJ',
  ROOF_E: 'https://drive.google.com/uc?export=view&id=17n_ATH7WaqC7UXu3jI0owKDRF-0gDlDT',
};

const normalizeRoof = (v) => {
  const r = String(v||'').trim().toUpperCase();
  if (r.startsWith('QR:ROOF_')) return r.replace('QR:','');
  if (r.startsWith('ROOF_')) return r;
  if (/^[A-E]$/.test(r)) return 'ROOF_'+r;
  const m = r.match(/\\[USER_ROOF:([A-E])\\]/);
  return m ? 'ROOF_'+m[1] : '';
};
const selectedRoof = normalizeRoof(inboundText);

// --- Collect images from tools ---
const imageUrls = [];
const seen = new Set();
const pushUrl = (u) => { if (typeof u==='string' && /^https?:\\/\\//i.test(u.trim()) && !seen.has(u.trim())) { seen.add(u.trim()); imageUrls.push(u.trim()); } };

if (roofMenu) pushUrl(ROOF_IMAGES.MENU);
if (selectedRoof && ROOF_IMAGES[selectedRoof]) pushUrl(ROOF_IMAGES[selectedRoof]);

const steps = Array.isArray(agentOutput.intermediateSteps) ? agentOutput.intermediateSteps : [];
for (const step of steps) {
  let data = step?.observation;
  if (typeof data === 'string') { try { data = JSON.parse(data); } catch(_) { data = null; } }
  const results = Array.isArray(data?.results) ? data.results : [];
  for (const row of results) {
    const brand = String(row?.brand||'').toLowerCase();
    if (brand && !brand.includes('thule') && !brand.includes('weathertech')) continue;
    pushUrl(row?.image_url);
  }
}
const imgPat = /\\[IMG:(https?:\\/\\/[^\\]\\s]+)\\]/g;
let match;
while ((match = imgPat.exec(outputText)) !== null) pushUrl(match[1]);

// --- Clean agent text ---
let cleanText = outputText
  .replace(/\\[IMG:https?:\\/\\/[^\\]\\s]+\\]/g, '')
  .replace(/\\[(ROOF_MENU|MAIN_MENU|WT_MENU)\\]/g, '')
  .replace(/\\n{3,}/g, '\\n\\n')
  .trim();

// --- Count product options for selection buttons ---
const countProducts = (t) => {
  const emoji = t.match(/\\d+️⃣/g) || [];
  if (emoji.length >= 2) return Math.min(emoji.length, 3);
  const lines = t.split('\\n').filter(l => /^\\s*(\\d+[.)\\]]|🔹|\\d+️⃣)/.test(l.trim()));
  return lines.length >= 2 ? Math.min(lines.length, 3) : 0;
};
const productOpts = countProducts(outputText);

// --- Build quick_replies config ---
let qrConfig = null;
if (roofMenu) {
  qrConfig = {
    options: ['A Riel elev.', 'B Riel alin.', 'C Punto fij.', 'D Techo liso', 'E Canal agua'],
    payloads: ['ROOF_A', 'ROOF_B', 'ROOF_C', 'ROOF_D', 'ROOF_E']
  };
  if (!cleanText || cleanText.length < 10) cleanText = 'Elige el tipo de techo de tu vehículo:';
} else if (mainMenu) {
  qrConfig = {
    options: ['Barras techo', 'Canasta/Baúl', 'Portabici', 'Alfombras WT', 'WhatsApp'],
    payloads: ['CAT_BARS', 'CAT_CARGO', 'CAT_BIKE', 'CAT_WT', 'WHATSAPP']
  };
  if (!cleanText || cleanText.length < 10) cleanText = '¡Hola! 👋 ¿Qué deseas cotizar?';
} else if (wtMenu) {
  qrConfig = {
    options: ['Por fila', 'Universal', 'WhatsApp'],
    payloads: ['WT_ROW', 'WT_UNIV', 'WHATSAPP']
  };
  if (!cleanText || cleanText.length < 10) cleanText = '¿Qué tipo de alfombra buscas?';
} else if (productOpts >= 2) {
  const opts = []; const pays = [];
  for (let i = 0; i < productOpts; i++) { opts.push((i+1)+'️⃣'); pays.push('SELECT_'+i); }
  opts.push('📞 WhatsApp'); pays.push('WHATSAPP');
  qrConfig = { options: opts, payloads: pays };
}

// --- Build final messages array ---
const messages = [];

// Images go FIRST as separate messages (Instagram requires this)
const maxImages = Math.min(imageUrls.length, 5);
for (let i = 0; i < maxImages; i++) {
  messages.push({ type: 'image', image_url: imageUrls[i], user_id });
}

// Text + quick_replies as ONE SINGLE message (THE CRITICAL FIX)
if (qrConfig) {
  messages.push({
    type: 'text_with_quick_replies',
    content: (cleanText || '¡Hola! ¿Cómo puedo ayudarte?').substring(0, 2000),
    options: qrConfig.options,
    payloads: qrConfig.payloads,
    user_id
  });
} else if (cleanText) {
  messages.push({ type: 'text', content: cleanText.substring(0, 2000), user_id });
}

if (messages.length === 0) {
  messages.push({ type: 'text', content: '¡Hola! ¿Cómo puedo ayudarte?', user_id });
}

return messages.map(m => ({ json: m }));`;


const BUILD_REQUEST_CODE = `// Build Instagram API request body — single message with quick_replies
const items = $input.all();
const fallbackUserId = (() => { try { return $('Filter & Normalize2').item.json.user_id; } catch(_) { return ''; } })();

return items.map((item) => {
  const msg = item.json || {};
  const userId = msg.user_id || fallbackUserId;
  const recipient = { id: userId };
  let body;

  if (msg.type === 'image' && msg.image_url) {
    body = JSON.stringify({
      recipient,
      message: { attachment: { type: 'image', payload: { url: msg.image_url, is_reusable: true } } }
    });

  } else if (msg.type === 'text_with_quick_replies' && msg.options && msg.options.length > 0) {
    // THE FIX: text + quick_replies in ONE message
    const qr = [];
    const maxBtns = Math.min(msg.options.length, 13);
    for (let i = 0; i < maxBtns; i++) {
      qr.push({
        content_type: 'text',
        title: String(msg.options[i]).substring(0, 20),
        payload: (msg.payloads && msg.payloads[i]) ? String(msg.payloads[i]).substring(0, 1000) : 'OPTION_' + i
      });
    }
    body = JSON.stringify({
      recipient,
      message: {
        text: String(msg.content || 'Elige una opción:').substring(0, 2000),
        quick_replies: qr
      }
    });

  } else {
    body = JSON.stringify({
      recipient,
      message: { text: String(msg.content || msg.text || '¡Hola!').substring(0, 1000) }
    });
  }

  return { json: { body, user_id: userId, message_type: msg.type || 'text' } };
});`;

main().catch(e => { console.error(e); process.exit(1); });
