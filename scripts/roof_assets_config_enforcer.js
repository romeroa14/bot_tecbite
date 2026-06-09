// Roof Assets Config + product accuracy enforcer (barras)
const input = $input.first().json || {};

const roof_assets = {
  source_folders: {
    menu_folder_url: 'https://drive.google.com/drive/u/0/folders/1btO_z9H6exE_3F6I979llJ7m_GQGwFjW',
    roof_types_folder_url: 'https://drive.google.com/drive/u/0/folders/1BrneB-uC_EYeVlGdwrUmLW0u2pgM8pdO',
  },
  menu: {
    label: 'Tipos de techo',
    public_url: 'https://drive.google.com/uc?export=view&id=1ett4opof8jzK9APUJtF71kXnEBwYYs-4',
  },
  items: {
    ROOF_A: { label: 'Riel elevado', public_url: 'https://drive.google.com/uc?export=view&id=1f7d0gXJ-PLWxUQ-yRxjlqRlAogqToDOR' },
    ROOF_B: { label: 'Riel integrado', public_url: 'https://drive.google.com/uc?export=view&id=15KVOsDgmM9DQw1vSDxY7bIuXaBl7i_WK' },
    ROOF_C: { label: 'Punto de fijación', public_url: 'https://drive.google.com/uc?export=view&id=1cFLKfJeqTKIx1hiC6lUFQzBCWyfUopp6' },
    ROOF_D: { label: 'Techo liso', public_url: 'https://drive.google.com/uc?export=view&id=1vbRJIfryNZr0TEPzrvml9LWhJ0k0DGMJ' },
    ROOF_E: { label: 'Canal de agua', public_url: 'https://drive.google.com/uc?export=view&id=17n_ATH7WaqC7UXu3jI0owKDRF-0gDlDT' },
  },
};

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

let inboundText = '';
try { inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim(); } catch (_) {}
if (!inboundText) inboundText = String(input.input || '').trim();

const normRoof = (v) => {
  const r = String(v || '').trim().toUpperCase();
  if (r.startsWith('QR:ROOF_')) return r.replace('QR:', '');
  if (r.startsWith('ROOF_')) return r;
  if (/^[A-E]$/.test(r)) return 'ROOF_' + r;
  return '';
};
const selectedRoof = normRoof(inboundText);

const unwrapFitment = (data) => {
  if (data == null) return null;
  if (typeof data === 'string') {
    try { return unwrapFitment(JSON.parse(data)); } catch (_) { return null; }
  }
  if (Array.isArray(data)) {
    for (const item of data) {
      const hit = unwrapFitment(item?.json || item);
      if (hit) return hit;
    }
    return null;
  }
  if (data?.json && typeof data.json === 'object') return unwrapFitment(data.json);
  if (data?.found === true && Array.isArray(data.results) && data.results.length) return data;
  return null;
};

const isToolErrorObservation = (obs) => {
  if (typeof obs !== 'string') return false;
  const s = obs.trim();
  return !s || s.startsWith('There was an error') || s.startsWith('Error:');
};

const parseFitment = (steps) => {
  let last = null;
  for (const step of steps || []) {
    const obs = step?.observation;
    if (isToolErrorObservation(obs)) continue;
    const hit = unwrapFitment(obs);
    if (hit) last = hit;
  }
  return last;
};

let agentJson = input;
try {
  const ag = $('AI Agent').first().json;
  if (ag && typeof ag === 'object') agentJson = { ...input, ...ag };
} catch (_) {}

const steps = Array.isArray(agentJson.intermediateSteps) ? agentJson.intermediateSteps : [];
let fitment = parseFitment(steps);

const loadFromToolNode = () => {
  const names = ['Tool: search_attributes_jsonb2', 'Tool: search_attributes_jsonb'];
  for (const name of names) {
    try {
      const items = $(name).all();
      for (const item of items) {
        const j = item?.json;
        if (j?.found === true && Array.isArray(j.results) && j.results.length) return j;
      }
    } catch (_) {}
  }
  return null;
};

if (!fitment?.found) fitment = unwrapFitment(agentJson);
if (!fitment?.found) fitment = loadFromToolNode();
const kit = fitment?.results?.[0] || fitment?.primary_recommendation || null;
const detailRequest = /\b(fotos?|detalle|precios?\s+(de\s+)?(las\s+)?barras|mas\s+info|más\s+info|opciones\s+de\s+barras)\b/i.test(fold(inboundText.replace(/^qr:/i, '')));
const roofTurn = /^QR:ROOF_[A-E]$/i.test(inboundText) || (/^ROOF_[A-E]$/i.test(selectedRoof) && fitment?.found);

let formatted_message = '';
let commercial_image = '';

const formatPrice = (p) => {
  const m = String(p || '').match(/([\d.]+)/);
  return m ? `$${m[1]} USD` : String(p || 'consultar');
};
const stockLabel = (s) => (s === 'in_stock' ? 'está en stock' : 'consulta disponibilidad con nosotros');
const uniqueBars = (items) => {
  const out = [];
  const seen = new Set();
  for (const item of items || []) {
    const sku = String(item?.sku || '').trim().toUpperCase();
    const title = fold(item?.title || '').replace(/\s+/g, ' ').trim();
    const key = sku || title;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
};

if (fitment?.found && kit && roofTurn && !detailRequest) {
  const q = fitment.query || {};
  formatted_message = `Para tu ${q.brand || ''} ${q.model || ''} ${q.year || ''} con ${String(fitment.roof_label || 'tu techo').toLowerCase()}, sí tenemos una solución compatible y ${stockLabel(kit.stock)}.`;
  if (fitment.ambiguous) formatted_message += ' Si tu carrocería es sedán u otra variante, cuéntanos y lo confirmamos.';
  formatted_message += '\n\nEsta imagen muestra la solución que recomendamos para tu tipo de techo.\n\nSi quieres, te muestro el detalle completo con opciones y precios, o te conecto con un asesor.';
  commercial_image = (selectedRoof && roof_assets.items[selectedRoof]?.public_url) || '';
} else if (fitment?.found && kit && detailRequest) {
  const lines = [`Kit ${String(kit.sku || '').replace(/TH$/i, '')}: ${kit.title} — ${formatPrice(kit.price)} (${stockLabel(kit.stock)})`];
  for (const b of uniqueBars(fitment.bars).slice(0, 3)) {
    lines.push(`${b.title} — ${formatPrice(b.price)} (${stockLabel(b.stock)})`);
  }
  formatted_message = lines.join('\n') + '\n\n¿Te interesa cotizar el kit, las barras o ambos? Si prefieres, también te conecto con un asesor.';
}

return [{
  json: {
    ...input,
    roof_assets,
    formatted_message,
    commercial_image,
    fitment_kit_sku: kit?.sku || null,
    enforcer_applied: !!formatted_message,
  },
}];
