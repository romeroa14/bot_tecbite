// Format Instagram Messages2 — product accuracy enforcer
const agentOutput = $input.first().json;
let outputText = agentOutput.output || agentOutput.text || '';

// Prefer AI Agent node for tool steps (Roof Assets Config may not forward all fields)
let agentRoot = agentOutput;
try {
  const ag = $('AI Agent').first().json;
  if (ag) {
    agentRoot = ag;
    if (!outputText) outputText = ag.output || ag.text || '';
  }
} catch (_) {}

const steps = Array.isArray(agentRoot.intermediateSteps) ? agentRoot.intermediateSteps : [];

let user_id = '';
let inboundText = '';
try { user_id = $('Filter & Normalize2').item.json.user_id || ''; } catch (_) {}
try { inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim(); } catch (_) {}
if (!inboundText) {
  try { inboundText = String(agentOutput.input || '').trim(); } catch (_) {}
}
if (!inboundText) {
  try { inboundText = String($('Save Early State').item.json.message_text || '').trim(); } catch (_) {}
}

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const outbound = fold(outputText);
const inboundFold = fold(inboundText.replace(/^qr:/i, ''));

let leadState = {};
try { leadState = $('Get Lead State').item.json || {}; } catch (_) {}

const explicitRoof = outputText.includes('[ROOF_MENU]');
const explicitMain = outputText.includes('[MAIN_MENU]');
const explicitWt = outputText.includes('[WT_MENU]');

const roofProductCtx = /\b(barras?|roof\s*racks?|portaequipajes?|portabici|canasta|ba[uú]l)\b/i.test(outputText + ' ' + inboundFold);
const wtProductCtx = /\b(alfombras?|floor\s*liners?|cargo\s+liners?|weathertech)\b/i.test(outputText + ' ' + inboundFold);
const roofCue = /\btipo\s+de\s+techo\b/i.test(outputText) || /\bOpci[oó]n\s+[A-E]\b/i.test(outputText);
const wtCue = /\b(fila|filas|universal|FloorLiner)\b/i.test(outputText) && /\b(tipo|cu[aá]l)\b/i.test(outputText);
const mainCue = /\b(qu[eé]|que)\s+(deseas|tipo)\b/i.test(outbound) || (
  [/barras?/i, /portabic/i, /alfombras?/i, /canasta|ba[uú]l/i].filter((r) => r.test(outputText)).length >= 2
);
const askingVehicle = /\b(marca|modelo|año)\b/i.test(outputText) && /\b(cu[aá]l|indic|dime|necesito)\b/i.test(outbound);

const ROOF_IMAGES = {
  MENU: 'https://drive.google.com/uc?export=view&id=1ett4opof8jzK9APUJtF71kXnEBwYYs-4',
  ROOF_A: 'https://drive.google.com/uc?export=view&id=1f7d0gXJ-PLWxUQ-yRxjlqRlAogqToDOR',
  ROOF_B: 'https://drive.google.com/uc?export=view&id=15KVOsDgmM9DQw1vSDxY7bIuXaBl7i_WK',
  ROOF_C: 'https://drive.google.com/uc?export=view&id=1cFLKfJeqTKIx1hiC6lUFQzBCWyfUopp6',
  ROOF_D: 'https://drive.google.com/uc?export=view&id=1vbRJIfryNZr0TEPzrvml9LWhJ0k0DGMJ',
  ROOF_E: 'https://drive.google.com/uc?export=view&id=17n_ATH7WaqC7UXu3jI0owKDRF-0gDlDT',
};

const normalizeRoof = (v) => {
  const r = String(v || '').trim().toUpperCase();
  if (r.startsWith('QR:ROOF_')) return r.replace('QR:', '');
  if (r.startsWith('ROOF_')) return r;
  if (/^[A-E]$/.test(r)) return 'ROOF_' + r;
  const m = r.match(/\[USER_ROOF:([A-E])\]/);
  return m ? 'ROOF_' + m[1] : '';
};
const selectedRoof = normalizeRoof(inboundText);
const detailRequest = /\b(fotos?|foto|detalle|detalles|precios?\s+(de\s+)?(las\s+)?barras|mas\s+info|más\s+info|mas\s+informacion|más\s+informaci[oó]n|opciones\s+de\s+barras|ver\s+barras|mostrar\s+barras)\b/i.test(inboundFold);

const normalizeVehicleText = (value) => String(value || '')
  .replace(/\[USER_ROOF:[A-E]\]/gi, '')
  .replace(/^QR:[A-Z0-9_]+$/i, '')
  .replace(/[(),]/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const extractVehicle = (value) => {
  const raw = normalizeVehicleText(value);
  const yearMatch = raw.match(/\b(19|20)\d{2}\b/);
  if (!yearMatch || yearMatch.index == null) return null;
  let beforeYear = raw.slice(0, yearMatch.index).trim();
  beforeYear = beforeYear.replace(/^(para|de|del|mi|vehiculo|vehículo|carro|camioneta|camion|camión|tengo|es|una|un)\s+/i, '');
  const tokens = beforeYear.split(/\s+/).filter(Boolean);
  if (tokens.length < 2) return null;
  return {
    make: tokens[0],
    model: tokens.slice(1).join(' '),
    year: Number(yearMatch[0]),
  };
};

const inferCategory = (text) => {
  const f = fold(text);
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:CAT_BARS')) return 'Barras techo';
  if (upper.includes('QR:CAT_CARGO')) return 'Canasta/Baúl';
  if (upper.includes('QR:CAT_BIKE')) return 'Portabici';
  if (upper.includes('QR:CAT_WT') || upper.includes('QR:WT_ROW') || upper.includes('QR:WT_UNIV')) return 'Alfombras WT';
  if (/\bbarras?\b/.test(f) || /roof\s*rack/.test(f) || /portaequipaje/.test(f)) return 'Barras techo';
  if (/\bcanasta\b/.test(f) || /\bbaul\b/.test(f) || /\bbaúl\b/.test(f)) return 'Canasta/Baúl';
  if (/\bportabici\b/.test(f) || /\bbici\b/.test(f)) return 'Portabici';
  if (/\balfombra\b/.test(f) || /weathertech/.test(f) || /floorliner/.test(f)) return 'Alfombras WT';
  return null;
};

const inboundVehicle = extractVehicle(inboundText);
const leadCategory = String(leadState.category || '').trim();
const leadStage = String(leadState.stage || '').trim() || 'greeting';
const currentCategory = inferCategory(inboundText) || leadCategory || '';
const currentVehicle = inboundVehicle || (
  leadState.make && leadState.model && leadState.year
    ? { make: leadState.make, model: leadState.model, year: Number(leadState.year) }
    : null
);
const needsRoofSelection = ['Barras techo', 'Canasta/Baúl'].includes(currentCategory);
const genericEntry = /^(hola|buenas|buenos dias|buenos días|buen dia|buen día|info|informacion|información|menu|menú)$/i.test(inboundFold);

let roofMenu = explicitRoof || (!explicitWt && !explicitMain && roofProductCtx && roofCue && !askingVehicle);
let wtMenu = explicitWt || (!explicitRoof && !explicitMain && wtProductCtx && wtCue && !askingVehicle);
let mainMenu = explicitMain || (!explicitRoof && !explicitWt && mainCue && !askingVehicle);

if (!roofMenu && !selectedRoof && !detailRequest && needsRoofSelection && currentVehicle && (leadStage === 'collect_roof' || roofCue)) {
  roofMenu = true;
}
if (!wtMenu && currentCategory === 'Alfombras WT' && (leadStage === 'collect_category' || wtCue)) {
  wtMenu = true;
}
if (!mainMenu && !roofMenu && !wtMenu && !currentCategory && (leadStage === 'greeting' || leadStage === 'collect_category' || genericEntry)) {
  mainMenu = true;
}

if (roofMenu && wtMenu) wtMenu = false;
if (roofMenu && mainMenu) mainMenu = false;
if (wtMenu && mainMenu) mainMenu = false;

const parseFitment = () => {
  let last = null;
  for (const step of steps) {
    let data = step?.observation;
    if (typeof data === 'string') {
      if (!data.trim() || data.startsWith('There was an error') || data.startsWith('Error:')) continue;
      try { data = JSON.parse(data); } catch (_) { continue; }
    }
    if (Array.isArray(data)) {
      data = data[0]?.json || data[0];
    }
    if (data?.json && typeof data.json === 'object') {
      data = data.json;
    }
    if (!data || typeof data !== 'object') continue;
    if (data.found === true && Array.isArray(data.results) && data.results.length) {
      last = data;
    }
  }
  return last;
};

const fitment = parseFitment();
const kit = fitment?.results?.[0] || fitment?.primary_recommendation || null;
const bars = Array.isArray(fitment?.bars) ? fitment.bars : [];

let leadRoof = '';
try { leadRoof = String($('Get Lead State').item.json.roof_type || '').trim(); } catch (_) {}

const roofSelectionInput = /^QR:ROOF_[A-E]$/i.test(inboundText.trim())
  || (/^QR:ROOF_[A-E]$/i.test(String(agentOutput.input || '').trim()));
const roofRecommendTurn = roofSelectionInput || (
  fitment?.found === true && kit && /^ROOF_[A-E]$/i.test(leadRoof)
);
const noRoofMatchTurn = roofSelectionInput && !fitment?.found && needsRoofSelection && !!currentVehicle;
const allowedSkus = new Set();
if (kit?.sku) allowedSkus.add(String(kit.sku).toUpperCase());
for (const b of bars) {
  if (b?.sku) allowedSkus.add(String(b.sku).toUpperCase());
}

const formatPrice = (priceRaw) => {
  const m = String(priceRaw || '').match(/([\d.]+)/);
  return m ? `$${m[1]} USD` : String(priceRaw || 'consultar');
};

const stockLabel = (stock) => {
  if (stock === 'in_stock') return 'está en stock';
  if (stock === 'out_of_stock') return 'no hay inventario en este momento';
  if (stock === 'discontinued') return 'está descontinuado';
  return 'consulta disponibilidad con nosotros';
};

const imageUrls = [];
const seen = new Set();
const pushUrl = (u) => {
  if (typeof u === 'string' && /^https?:\/\//i.test(u.trim()) && !seen.has(u.trim())) {
    seen.add(u.trim());
    imageUrls.push(u.trim());
  }
};

if (noRoofMatchTurn) {
  roofMenu = true;
  wtMenu = false;
  mainMenu = false;
}

if (roofMenu) pushUrl(ROOF_IMAGES.MENU);
if (agentOutput.commercial_image && fitment?.found) {
  pushUrl(agentOutput.commercial_image);
} else if (selectedRoof && ROOF_IMAGES[selectedRoof] && fitment?.found) {
  pushUrl(ROOF_IMAGES[selectedRoof]);
}

let cleanText = outputText
  .replace(/\[IMG:https?:\/\/[^\]\s]+\]/g, '')
  .replace(/\[(ROOF_MENU|MAIN_MENU|WT_MENU)\]/g, '')
  .split('\n')
  .filter((line) => !line.trim().startsWith('[STATE_UPDATE]'))
  .join('\n')
  .replace(/\n{3,}/g, '\n\n')
  .trim();

// Prefer enforcer output from Roof Assets Config
if (agentOutput.enforcer_applied && agentOutput.formatted_message) {
  cleanText = String(agentOutput.formatted_message);
}

// --- Product accuracy enforcer (barras) ---
if (noRoofMatchTurn) {
  const make = currentVehicle?.make || leadState.make || '';
  const model = currentVehicle?.model || leadState.model || '';
  const yr = currentVehicle?.year || leadState.year || '';
  cleanText = `No encontré una compatibilidad confirmada con esa selección de techo para tu ${make} ${model} ${yr}. Revisemos el tipo de techo antes de recomendarte una solución.`;
} else if (fitment?.found && kit && roofRecommendTurn && !detailRequest) {
  const q = fitment.query || {};
  const make = q.brand || '';
  const model = q.model || '';
  const yr = q.year || '';
  const roofLabel = fitment.roof_label || 'tu tipo de techo';
  cleanText = `Para tu ${make} ${model} ${yr} con ${String(roofLabel).toLowerCase()}, sí tenemos una solución compatible y ${stockLabel(kit.stock)}.`;

  if (fitment.ambiguous) {
    cleanText += ' Si tu vehículo es sedán u otra carrocería, cuéntanos y lo confirmamos.';
  }

  cleanText += '\n\nEsta imagen muestra la solución que recomendamos para tu tipo de techo.\n\nSi quieres, te muestro el detalle completo con opciones y precios, o te conecto con un asesor.';

  imageUrls.length = 0;
  seen.clear();
  if (selectedRoof && ROOF_IMAGES[selectedRoof]) pushUrl(ROOF_IMAGES[selectedRoof]);
} else if (fitment?.found && kit && detailRequest) {
  const q = fitment.query || {};
  const lines = [`Kit ${String(kit.sku || '').replace(/TH$/i, '')}: ${kit.title} — ${formatPrice(kit.price)} (${stockLabel(kit.stock)})`];
  const topBars = bars.slice(0, 3);
  for (const b of topBars) {
    lines.push(`${b.title} — ${formatPrice(b.price)} (${stockLabel(b.stock)})`);
    if (b.image_url) pushUrl(b.image_url);
  }
  if (!topBars.length) {
    lines.push('Las barras compatibles están en inventario; un asesor te puede confirmar el par exacto para tu kit.');
  }
  cleanText = lines.join('\n') + '\n\n¿Te interesa cotizar el kit, las barras o ambos? Si prefieres, también te conecto con un asesor.';
} else if (fitment?.found && kit) {
  // Strip SKUs/prices not from tool when fitment exists
  const skuPat = /\b\d{4}TH\b/gi;
  cleanText = cleanText.replace(skuPat, (m) => (allowedSkus.has(m.toUpperCase()) ? m : ''));
  cleanText = cleanText.replace(/\n{3,}/g, '\n\n').trim();
}

// Collect tool images only for non-roof-selection turns
if (!(fitment?.found && kit && roofRecommendTurn && !detailRequest)) {
  for (const step of steps) {
    let data = step?.observation;
    if (typeof data === 'string') { try { data = JSON.parse(data); } catch (_) { data = null; } }
    const results = Array.isArray(data?.results) ? data.results : [];
    for (const row of results.slice(0, 1)) {
      pushUrl(row?.image_url);
    }
    if (Array.isArray(data?.bars) && detailRequest) {
      for (const b of data.bars.slice(0, 3)) pushUrl(b?.image_url);
    }
  }
}

const imgPat = /\[IMG:(https?:\/\/[^\]\s]+)\]/g;
let match;
while ((match = imgPat.exec(outputText)) !== null) {
  if (!(fitment?.found && kit && roofRecommendTurn && !detailRequest)) pushUrl(match[1]);
}

const countProducts = (t) => {
  const emoji = t.match(/\d+️⃣/g) || [];
  if (emoji.length >= 2) return Math.min(emoji.length, 3);
  const lines = t.split('\n').filter((l) => /^\s*(\d+[.)\]]|🔹|\d+️⃣)/.test(l.trim()));
  return lines.length >= 2 ? Math.min(lines.length, 3) : 0;
};
const productOpts = countProducts(cleanText);

let qrConfig = null;
if (roofMenu) {
  qrConfig = {
    options: ['A Riel elev.', 'B Riel alin.', 'C Punto fij.', 'D Techo liso', 'E Canal agua'],
    payloads: ['ROOF_A', 'ROOF_B', 'ROOF_C', 'ROOF_D', 'ROOF_E'],
  };
  if (!cleanText || cleanText.length < 10) cleanText = 'Elige el tipo de techo de tu vehículo:';
} else if (mainMenu) {
  qrConfig = {
    options: ['Barras techo', 'Canasta/Baúl', 'Portabici', 'Alfombras WT', 'WhatsApp'],
    payloads: ['CAT_BARS', 'CAT_CARGO', 'CAT_BIKE', 'CAT_WT', 'WHATSAPP'],
  };
  if (!cleanText || cleanText.length < 10) cleanText = '¡Hola! 👋 ¿Qué deseas cotizar?';
} else if (wtMenu) {
  qrConfig = {
    options: ['Por fila', 'Universal', 'WhatsApp'],
    payloads: ['WT_ROW', 'WT_UNIV', 'WHATSAPP'],
  };
  if (!cleanText || cleanText.length < 10) cleanText = '¿Qué tipo de alfombra buscas?';
} else if (productOpts >= 2 && !fitment?.found) {
  const opts = [];
  const pays = [];
  for (let i = 0; i < productOpts; i++) { opts.push((i + 1) + '️⃣'); pays.push('SELECT_' + i); }
  opts.push('📞 WhatsApp');
  pays.push('WHATSAPP');
  qrConfig = { options: opts, payloads: pays };
}

const messages = [];
const maxImages = Math.min(imageUrls.length, 5);
for (let i = 0; i < maxImages; i++) {
  messages.push({ type: 'image', image_url: imageUrls[i], user_id });
}

if (qrConfig) {
  messages.push({
    type: 'text_with_quick_replies',
    content: (cleanText || '¡Hola!').substring(0, 2000),
    options: qrConfig.options,
    payloads: qrConfig.payloads,
    user_id,
  });
} else if (cleanText) {
  messages.push({ type: 'text', content: cleanText.substring(0, 2000), user_id });
}

if (messages.length === 0) {
  messages.push({ type: 'text', content: '¡Hola! ¿Cómo puedo ayudarte?', user_id });
}

return messages.map((m) => ({ json: m }));
