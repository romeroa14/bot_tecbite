// Prepare Fitment Query — build direct attributes lookup from lead state + inbound
const agentOutput = $input.first().json || {};

let inboundText = '';
try { inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim(); } catch (_) {}

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

let leadState = {};
try { leadState = $('Get Lead State').item.json || {}; } catch (_) {}

const normRoof = (v) => {
  const r = String(v || '').trim().toUpperCase();
  if (r.startsWith('QR:ROOF_')) return r.replace('QR:', '');
  if (r.startsWith('ROOF_')) return r;
  if (/^[A-E]$/.test(r)) return `ROOF_${r}`;
  return '';
};

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
  if (/\bbarras?\b/.test(f) || /roof\s*rack/.test(f) || /portaequipaje/.test(f)) return 'Barras techo';
  if (/\bcanasta\b/.test(f) || /\bbaul\b/.test(f) || /\bbaúl\b/.test(f)) return 'Canasta/Baúl';
  return null;
};

const inboundVehicle = extractVehicle(inboundText);
const category = inferCategory(inboundText) || String(leadState.category || '').trim();
const vehicle = inboundVehicle || (
  leadState.make && leadState.model && leadState.year
    ? { make: leadState.make, model: leadState.model, year: Number(leadState.year) }
    : null
);
const roofType = normRoof(inboundText) || normRoof(leadState.roof_type);
const needsRoof = ['Barras techo', 'Canasta/Baúl'].includes(category);
const detailRequest = /\b(fotos?|foto|detalle|detalles|detalles?\s+completos?|precios?\s+(de\s+)?(las\s+)?barras|mas\s+info|más\s+info|opciones\s+de\s+barras|muestrame|mu[eé]strame|desglosa)\b/i.test(fold(inboundText.replace(/^qr:/i, '')));
const roofSelection = /^QR:ROOF_[A-E]$/i.test(inboundText);

let fitment_query = null;
if (needsRoof && vehicle?.make && vehicle?.model && vehicle?.year && roofType && (roofSelection || detailRequest)) {
  fitment_query = {
    brand: vehicle.make,
    model: vehicle.model,
    year: vehicle.year,
    roof_type: roofType,
  };
}

return [{
  json: {
    ...agentOutput,
    fitment_query,
    fitment_lookup_attempted: !!fitment_query,
  },
}];
