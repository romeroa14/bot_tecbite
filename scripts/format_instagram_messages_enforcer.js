// Format Instagram Messages2 — product accuracy enforcer
const SALES_ADVISORS = [
  {
    id: 'DAVE',
    name: 'Dave',
    qrLabel: 'Dave',
    qrPayload: 'ADV_DAVE',
    phone: '50769880471',
    waText: 'Hola Dave, buen día. Te contacto de Tecbite porque estoy interesado en algunos productos Thule y WeatherTech y quisiera recibir tu asesoría.',
  },
  {
    id: 'EDUARDO',
    name: 'Eduardo',
    qrLabel: 'Eduardo',
    qrPayload: 'ADV_EDUARDO',
    phone: '50769504792',
    waText: 'Hola Eduardo, buen día. Te escribo porque necesito tu asistencia con unos productos Thule y WeatherTech. ¿Me puedes orientar por favor?',
  },
];
const buildWaUrl = (phone, text) => `https://api.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(text)}`;
const findAdvisorByPayload = (value) => {
  const inboundUpper = String(value || '').trim().toUpperCase();
  return SALES_ADVISORS.find((a) => inboundUpper === `QR:${a.qrPayload}`) || null;
};
const stripAdvisorLinks = (text) => String(text || '')
  .replace(/\[ADVISOR_MENU\]/gi, '')
  .replace(/https?:\/\/(?:api\.)?whatsapp\.com\/send[^\s)\]]+/gi, '')
  .replace(/^\s*[-•*]\s*(Dave|Eduardo)\s*:?\s*$/gim, '')
  .replace(/\n{3,}/g, '\n\n')
  .trim();

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
const detailRequest = /\b(fotos?|foto|detalle|detalles|detalles?\s+completos?|precios?\s+(de\s+)?(las\s+)?barras|mas\s+info|más\s+info|mas\s+informacion|más\s+informaci[oó]n|opciones\s+de\s+barras|ver\s+barras|mostrar\s+barras|muestrame|mu[eé]strame|desglosa)\b/i.test(inboundFold);

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
  if (/\balfombra\b/.test(f) || /weathertech/.test(f) || /floorliner/.test(f) || /cargo\s*liner/.test(f)) return 'Alfombras WT';
  return null;
};

const normalizeComparable = (value) => fold(value).replace(/[^a-z0-9]/g, '');

const yearMatchesTitle = (title, year) => {
  const y = Number(year);
  if (!Number.isFinite(y)) return true;
  const t = String(title || '');
  if (new RegExp(`\\b${y}\\b`).test(t)) return true;
  for (const token of t.match(/\b((19|20)\d{2})\+(?!\d)/g) || []) {
    const start = Number(token.slice(0, 4));
    if (y >= start) return true;
  }
  for (const range of t.match(/\b(19|20)\d{2}\s*-\s*((19|20)\d{2}|\+)\b/g) || []) {
    const m = range.match(/(\d{4})\s*-\s*(\+|(\d{4}))/);
    if (!m) continue;
    const start = Number(m[1]);
    const end = m[2] === '+' ? 9999 : Number(m[2]);
    if (y >= start && y <= end) return true;
  }
  return false;
};

const filterWtForVehicle = (results, vehicle, wtType) => {
  const makeCmp = normalizeComparable(vehicle?.make);
  const modelCmp = normalizeComparable(vehicle?.model);
  const year = Number(vehicle?.year);
  const dedup = new Set();
  const out = [];
  for (const row of results || []) {
    const title = String(row?.title || '');
    const folded = fold(title);
    const titleCmp = normalizeComparable(title);
    if (makeCmp && !titleCmp.includes(makeCmp)) continue;
    if (modelCmp && !titleCmp.includes(modelCmp)) continue;
    if (!yearMatchesTitle(title, year)) continue;
    if (wtType === 'row' && /\buniversal\b/i.test(folded)) continue;
    if (wtType === 'univ' && !/\buniversal\b/i.test(folded)) continue;
    const sku = String(row?.sku || row?.product_sku || '').trim().toUpperCase();
    if (sku && dedup.has(sku)) continue;
    if (sku) dedup.add(sku);
    out.push(row);
  }
  out.sort((a, b) => {
    const rank = (s) => (s === 'in_stock' ? 0 : s === 'out_of_stock' ? 1 : 2);
    return rank(a?.stock) - rank(b?.stock);
  });
  return out.slice(0, 3);
};

const loadWtProducts = () => {
  let attempted = false;
  let wtType = 'row';
  try {
    const prep = $('Prepare Fitment Query').first().json;
    attempted = !!prep.wt_lookup_attempted;
    wtType = prep.wt_query?.wt_type || 'row';
  } catch (_) {}
  if (!attempted) return [];
  try {
    const raw = $('WT Product Lookup').first().json;
    const results = Array.isArray(raw?.results) ? raw.results : [];
    const vehicle = currentVehicle || {
      make: leadState.make,
      model: leadState.model,
      year: Number(leadState.year),
    };
    return filterWtForVehicle(results, vehicle, wtType);
  } catch (_) {}
  return [];
};

const parseFlowTag = (tag) => {
  const s = String(tag || '');
  if (!s.startsWith('flow:')) return {};
  const out = {};
  for (const part of s.slice(5).split(',')) {
    const [k, v] = part.split('=');
    if (k && v) out[k.trim()] = v.trim();
  }
  return out;
};

const inferCargoType = (text, flowState = {}) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:CARGO_CANASTA')) return 'canasta';
  if (upper.includes('QR:CARGO_BAUL')) return 'baul';
  const f = fold(text);
  if (/\bcanasta\b/.test(f) && !/\bbaul\b/.test(f)) return 'canasta';
  if (/\bbaul\b/.test(f) || /\bbaúl\b/.test(f)) return 'baul';
  return flowState.cargo || '';
};

const inferBikeMount = (text, flowState = {}) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:BIKE_M_ROOF')) return 'techo';
  if (upper.includes('QR:BIKE_M_TRUNK')) return 'joroba';
  if (upper.includes('QR:BIKE_M_PICKUP')) return 'pickup';
  if (upper.includes('QR:BIKE_M_BALL')) return 'bola';
  if (upper.includes('QR:BIKE_M_HITCH')) return 'hitch';
  if (upper.includes('QR:BIKE_M_ACC')) return 'acc';
  return flowState.mount || '';
};

const inferBikeType = (text, flowState = {}) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:BIKE_T_ELEC')) return 'electric';
  if (upper.includes('QR:BIKE_T_MTB')) return 'mtb';
  if (upper.includes('QR:BIKE_T_ROAD')) return 'ruta';
  return flowState.type || '';
};

const loadCatalogProducts = (nodeName, attemptedField) => {
  let attempted = false;
  try {
    attempted = !!$('Prepare Fitment Query').first().json[attemptedField];
  } catch (_) {}
  if (!attempted) return [];
  const unwrap = (raw) => {
    if (!raw) return null;
    if (Array.isArray(raw)) raw = raw[0];
    if (raw?.json && typeof raw.json === 'object' && !Array.isArray(raw.json)) raw = raw.json;
    return raw;
  };
  try {
    const raw = unwrap($(nodeName).first().json);
    if (!raw || raw.found === false || !Array.isArray(raw.results)) return [];
    return raw.results.filter((r) => r?.image_url || r?.title);
  } catch (_) {}
  return [];
};

const flowState = parseFlowTag(leadState.product_tag);
const cargoType = inferCargoType(inboundText, flowState);
const bikeMount = inferBikeMount(inboundText, flowState);
const bikeType = inferBikeType(inboundText, flowState);
const bikeBars = (() => {
  if (/^QR:BIKE_BARS_YES$/i.test(inboundText)) return 'yes';
  if (/^QR:BIKE_BARS_NO$/i.test(inboundText)) return 'no';
  return flowState.bars || '';
})();

const inboundVehicle = extractVehicle(inboundText);
const leadCategory = String(leadState.category || '').trim();
const leadStage = String(leadState.stage || '').trim() || 'greeting';
const currentCategory = inferCategory(inboundText) || leadCategory || '';
const wtSelectionInput = /^QR:WT_(ROW|UNIV)$/i.test(inboundText);
const currentVehicle = inboundVehicle || (
  leadState.make && leadState.model && leadState.year
    ? { make: leadState.make, model: leadState.model, year: Number(leadState.year) }
    : null
);
const needsRoofSelection = currentCategory === 'Barras techo';
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
if (wtSelectionInput && currentCategory === 'Alfombras WT') wtMenu = false;

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

const loadFitmentFromToolNode = () => {
  const names = ['Tool: search_attributes_jsonb2', 'Tool: search_attributes_jsonb'];
  for (const name of names) {
    try {
      for (const item of $(name).all()) {
        const j = item?.json;
        if (j?.found === true && Array.isArray(j.results) && j.results.length) return j;
      }
    } catch (_) {}
  }
  return null;
};

const loadFitmentFromLookupNode = () => {
  let attempted = false;
  try {
    attempted = !!$('Prepare Fitment Query').first().json.fitment_lookup_attempted;
  } catch (_) {}
  if (!attempted) return null;
  try {
    const j = $('Fitment Lookup').first().json;
    if (j && typeof j === 'object' && ('found' in j)) return j;
  } catch (_) {}
  return null;
};

let fitment = parseFitment();
if (!fitment?.found) fitment = loadFitmentFromLookupNode();
if (!fitment?.found) fitment = loadFitmentFromToolNode();
const kit = fitment?.results?.[0] || fitment?.primary_recommendation || null;
const bars = Array.isArray(fitment?.bars) ? fitment.bars : [];

let leadRoof = '';
try { leadRoof = String($('Get Lead State').item.json.roof_type || '').trim(); } catch (_) {}

const roofSelectionInput = /^QR:ROOF_[A-E]$/i.test(inboundText.trim())
  || (/^QR:ROOF_[A-E]$/i.test(String(agentOutput.input || '').trim()));
const roofRecommendTurn = needsRoofSelection && (roofSelectionInput || (
  fitment?.found === true && kit && /^ROOF_[A-E]$/i.test(leadRoof) && !wtSelectionInput
));
let fitmentLookupAttempted = false;
try { fitmentLookupAttempted = !!$('Prepare Fitment Query').first().json.fitment_lookup_attempted; } catch (_) {}
const noRoofMatchTurn = roofSelectionInput && fitmentLookupAttempted && fitment?.found === false && needsRoofSelection && !!currentVehicle;
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
const uniqueBars = (items) => {
  const out = [];
  const seenBars = new Set();
  for (const item of items || []) {
    const sku = String(item?.sku || '').trim().toUpperCase();
    const title = fold(item?.title || '').replace(/\s+/g, ' ').trim();
    const key = sku || title;
    if (!key || seenBars.has(key)) continue;
    seenBars.add(key);
    out.push(item);
  }
  return out;
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

let cargoLookupAttempted = false;
let bikeLookupAttempted = false;
try { cargoLookupAttempted = !!$('Prepare Fitment Query').first().json.cargo_lookup_attempted; } catch (_) {}
try { bikeLookupAttempted = !!$('Prepare Fitment Query').first().json.bike_lookup_attempted; } catch (_) {}

const wtProducts = currentCategory === 'Alfombras WT' ? loadWtProducts() : [];
const wtRecommendTurn = currentCategory === 'Alfombras WT' && wtProducts.length > 0 && (wtSelectionInput || detailRequest);
const cargoProducts = currentCategory === 'Canasta/Baúl' ? loadCatalogProducts('Thule Cargo Lookup', 'cargo_lookup_attempted') : [];
const bikeProducts = currentCategory === 'Portabici' ? loadCatalogProducts('Thule Bike Lookup', 'bike_lookup_attempted') : [];

let cargoMenu = false;
let bikeMountMenu = false;
let bikeTypeMenu = false;
let bikeBarsMenu = false;
if (currentCategory === 'Canasta/Baúl' && currentVehicle && !cargoType) {
  cargoMenu = true;
  roofMenu = false;
  mainMenu = false;
  wtMenu = false;
}
if (currentCategory === 'Portabici' && currentVehicle && !bikeMount) {
  bikeMountMenu = true;
  roofMenu = false;
  mainMenu = false;
  wtMenu = false;
  cargoMenu = false;
}
if (currentCategory === 'Portabici' && currentVehicle && bikeMount && !bikeType) {
  bikeTypeMenu = true;
  bikeMountMenu = false;
  roofMenu = false;
}
if (currentCategory === 'Portabici' && bikeMount === 'techo' && bikeType && !bikeBars) {
  bikeBarsMenu = true;
  bikeTypeMenu = false;
  roofMenu = false;
}
if (currentCategory !== 'Barras techo') {
  roofMenu = false;
}

const cargoRecommendTurn = currentCategory === 'Canasta/Baúl' && !!cargoType && !!currentVehicle && !cargoMenu;
const bikeRecommendTurn = currentCategory === 'Portabici' && !!bikeMount && !!bikeType
  && (bikeMount !== 'techo' || bikeBars === 'yes')
  && !bikeMountMenu && !bikeTypeMenu && !bikeBarsMenu;

let bikeBarsRedirectMenu = false;

if (roofMenu && needsRoofSelection) pushUrl(ROOF_IMAGES.MENU);
if (agentOutput.commercial_image && fitment?.found && needsRoofSelection) {
  pushUrl(agentOutput.commercial_image);
} else if (selectedRoof && ROOF_IMAGES[selectedRoof] && fitment?.found && needsRoofSelection) {
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

// Prefer enforcer output from Roof Assets Config (barras only)
if (agentOutput.enforcer_applied && agentOutput.formatted_message && !cargoRecommendTurn && !bikeRecommendTurn) {
  cleanText = String(agentOutput.formatted_message);
}

// --- Product accuracy enforcer ---
if (cargoRecommendTurn) {
  const label = cargoType === 'canasta' ? 'canastas de techo Thule' : 'baúles de techo Thule';
  const make = currentVehicle?.make || leadState.make || '';
  const model = currentVehicle?.model || leadState.model || '';
  const yr = currentVehicle?.year || leadState.year || '';
  if (cargoProducts.length > 0) {
    const lines = [`Estas son nuestras opciones de ${label}:`];
    const emoji = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣'];
    imageUrls.length = 0;
    seen.clear();
    cargoProducts.forEach((p, i) => {
      lines.push(`${emoji[i] || '🔹'} ${p.title} — ${formatPrice(p.price)} (${stockLabel(p.stock)})`);
      if (p.image_url) pushUrl(p.image_url);
    });
    cleanText = lines.join('\n') + '\n\n¿Cuál te interesa cotizar? Un asesor puede confirmar compatibilidad con tu vehículo.';
  } else {
    imageUrls.length = 0;
    seen.clear();
    cleanText = `Para tu ${make} ${model} ${yr}, no encontramos ${label} en inventario en este momento. Un asesor puede confirmar disponibilidad y compatibilidad.`;
  }
} else if (bikeRecommendTurn) {
  const mountLabels = { techo: 'techo', joroba: 'maletero', pickup: 'pick-up', bola: 'bola', hitch: 'remolque', acc: 'accesorios' };
  const make = currentVehicle?.make || leadState.make || '';
  const model = currentVehicle?.model || leadState.model || '';
  const yr = currentVehicle?.year || leadState.year || '';
  if (bikeProducts.length > 0) {
    const lines = [`Portabicicletas Thule (${mountLabels[bikeMount] || bikeMount}):`];
    const emoji = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣'];
    imageUrls.length = 0;
    seen.clear();
    bikeProducts.forEach((p, i) => {
      lines.push(`${emoji[i] || '🔹'} ${p.title} — ${formatPrice(p.price)} (${stockLabel(p.stock)})`);
      if (p.image_url) pushUrl(p.image_url);
    });
    cleanText = lines.join('\n') + '\n\nUn asesor verificará compatibilidad con tu vehículo y te enviará la cotización.';
  } else {
    imageUrls.length = 0;
    seen.clear();
    cleanText = `Para tu ${make} ${model} ${yr}, no encontramos portabicicletas Thule (${mountLabels[bikeMount] || bikeMount}) en inventario ahora. Un asesor puede ayudarte con opciones compatibles.`;
  }
} else if (/^QR:BIKE_BARS_NO$/i.test(inboundText) && bikeMount === 'techo') {
  cleanText = 'Para un portabicicleta de techo primero necesitas barras. ¿Quieres cotizar barras de techo para tu vehículo?';
  bikeBarsRedirectMenu = true;
  roofMenu = false;
  mainMenu = false;
  bikeBarsMenu = false;
} else if (wtRecommendTurn) {
  const make = currentVehicle?.make || leadState.make || '';
  const model = currentVehicle?.model || leadState.model || '';
  const yr = currentVehicle?.year || leadState.year || '';
  const lines = [`Para tu ${make} ${model} ${yr}, estas son opciones WeatherTech compatibles:`];
  const emoji = ['1️⃣', '2️⃣', '3️⃣'];
  imageUrls.length = 0;
  seen.clear();
  wtProducts.forEach((p, i) => {
    lines.push(`${emoji[i] || '🔹'} *${p.title}* — ${formatPrice(p.price)} (${stockLabel(p.stock)})`);
    if (p.image_url) pushUrl(p.image_url);
  });
  cleanText = lines.join('\n') + '\n\n¿Cuál te interesa cotizar o quieres que te conecte con un asesor?';
} else if (noRoofMatchTurn) {
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
  const topBars = uniqueBars(bars).slice(0, 3);
  imageUrls.length = 0;
  seen.clear();
  if (kit.image_url) pushUrl(kit.image_url);
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

const enforcerControlledImages = !!(wtRecommendTurn || cargoRecommendTurn || bikeRecommendTurn || (needsRoofSelection && fitment?.found && kit && (
  (roofRecommendTurn && !detailRequest) || detailRequest
)));

// Collect tool images only when enforcer did not already curate images
if (!enforcerControlledImages) {
  for (const step of steps) {
    let data = step?.observation;
    if (typeof data === 'string') { try { data = JSON.parse(data); } catch (_) { data = null; } }
    const results = Array.isArray(data?.results) ? data.results : [];
    for (const row of results.slice(0, 1)) {
      pushUrl(row?.image_url);
    }
  }
}

const imgPat = /\[IMG:(https?:\/\/[^\]\s]+)\]/g;
let match;
while ((match = imgPat.exec(outputText)) !== null) {
  if (!enforcerControlledImages) pushUrl(match[1]);
}

const countProducts = (t) => {
  const emoji = t.match(/\d+️⃣/g) || [];
  if (emoji.length >= 2) return Math.min(emoji.length, 3);
  const lines = t.split('\n').filter((l) => /^\s*(\d+[.)\]]|🔹|\d+️⃣)/.test(l.trim()));
  return lines.length >= 2 ? Math.min(lines.length, 3) : 0;
};
const productOpts = countProducts(cleanText);

let qrConfig = null;
if (bikeBarsRedirectMenu) {
  qrConfig = {
    options: ['Sí, cotizar barras', 'WhatsApp'],
    payloads: ['CAT_BARS', 'WHATSAPP'],
  };
} else if (roofMenu) {
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
} else if (cargoMenu) {
  qrConfig = {
    options: ['Canasta', 'Baúl', 'WhatsApp'],
    payloads: ['CARGO_CANASTA', 'CARGO_BAUL', 'WHATSAPP'],
  };
  cleanText = 'Perfecto 🙌 ¿Buscas canasta de techo o baúl?';
} else if (bikeMountMenu) {
  qrConfig = {
    options: ['Techo', 'Joroba', 'Pick-up', 'Bola', 'Remolque', 'WhatsApp'],
    payloads: ['BIKE_M_ROOF', 'BIKE_M_TRUNK', 'BIKE_M_PICKUP', 'BIKE_M_BALL', 'BIKE_M_HITCH', 'WHATSAPP'],
  };
  cleanText = '¿Qué tipo de portabicicleta buscas?';
} else if (bikeTypeMenu) {
  qrConfig = {
    options: ['Ruta', 'MTB', 'Eléctrica', 'WhatsApp'],
    payloads: ['BIKE_T_ROAD', 'BIKE_T_MTB', 'BIKE_T_ELEC', 'WHATSAPP'],
  };
  cleanText = '¿Qué tipo de bicicleta utilizas?';
} else if (bikeBarsMenu) {
  qrConfig = {
    options: ['Sí, tengo barras', 'No, cotizar barras', 'WhatsApp'],
    payloads: ['BIKE_BARS_YES', 'BIKE_BARS_NO', 'WHATSAPP'],
  };
  cleanText = 'Para portabicicleta de techo necesitas barras instaladas. ¿Tu auto cuenta con barras?';
} else if (productOpts >= 2 && !fitment?.found) {
  const opts = [];
  const pays = [];
  for (let i = 0; i < productOpts; i++) { opts.push((i + 1) + '️⃣'); pays.push('SELECT_' + i); }
  opts.push('📞 WhatsApp');
  pays.push('WHATSAPP');
  qrConfig = { options: opts, payloads: pays };
}

const inboundUpper = inboundText.trim().toUpperCase();
const selectedAdvisor = findAdvisorByPayload(inboundText);
const advisorMenuRequested = !!(
  selectedAdvisor === null && (
    inboundUpper === 'QR:WHATSAPP'
    || outputText.includes('[ADVISOR_MENU]')
    || /api\.whatsapp\.com\/send/i.test(outputText)
    || /\[ADVISOR_MENU\]/i.test(outputText)
  )
);

cleanText = stripAdvisorLinks(cleanText);

const messages = [];
const maxImages = Math.min(imageUrls.length, 5);
for (let i = 0; i < maxImages; i++) {
  messages.push({ type: 'image', image_url: imageUrls[i], user_id });
}

if (selectedAdvisor) {
  messages.push({
    type: 'button_template',
    content: `Te conecto con ${selectedAdvisor.name}. Toca el botón para abrir WhatsApp.`,
    buttons: [{
      title: `WhatsApp ${selectedAdvisor.name}`,
      url: buildWaUrl(selectedAdvisor.phone, selectedAdvisor.waText),
    }],
    user_id,
  });
} else if (advisorMenuRequested) {
  if (!cleanText || cleanText.length < 10) {
    cleanText = 'Con gusto te conecto con un asesor. ¿Con quién prefieres hablar?';
  }
  messages.push({
    type: 'text_with_quick_replies',
    content: cleanText.substring(0, 2000),
    options: SALES_ADVISORS.map((a) => a.qrLabel),
    payloads: SALES_ADVISORS.map((a) => a.qrPayload),
    user_id,
  });
} else if (qrConfig) {
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
