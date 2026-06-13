// Prepare Fitment Query — build direct product lookups from lead state + inbound
const agentOutput = $input.first().json || {};

let inboundText = '';
try { inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim(); } catch (_) {}

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

let leadState = {};
try { leadState = $('Get Lead State').item.json || {}; } catch (_) {}

const inferProductCategory = (text, leadCategory = '') => {
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
  return leadCategory || '';
};

const inferCargoType = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:CARGO_CANASTA')) return 'canasta';
  if (upper.includes('QR:CARGO_BAUL')) return 'baul';
  const f = fold(text);
  if (/\bcanasta\b/.test(f) && !/\bbaul\b/.test(f)) return 'canasta';
  if (/\bbaul\b/.test(f) || /\bbaúl\b/.test(f)) return 'baul';
  return '';
};

const inferBikeMount = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:BIKE_M_ROOF')) return 'techo';
  if (upper.includes('QR:BIKE_M_TRUNK')) return 'joroba';
  if (upper.includes('QR:BIKE_M_PICKUP')) return 'pickup';
  if (upper.includes('QR:BIKE_M_BALL')) return 'bola';
  if (upper.includes('QR:BIKE_M_HITCH')) return 'hitch';
  if (upper.includes('QR:BIKE_M_ACC')) return 'acc';
  return '';
};

const inferBikeType = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:BIKE_T_ELEC')) return 'electric';
  if (upper.includes('QR:BIKE_T_MTB')) return 'mtb';
  if (upper.includes('QR:BIKE_T_ROAD')) return 'ruta';
  return '';
};

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

const inferWtType = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:WT_UNIV')) return 'univ';
  if (upper.includes('QR:WT_ROW')) return 'row';
  return '';
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

const inboundVehicle = extractVehicle(inboundText);
const category = inferProductCategory(inboundText, String(leadState.category || '').trim());
const flowState = parseFlowTag(leadState.product_tag);
const vehicle = inboundVehicle || (
  leadState.make && leadState.model && leadState.year
    ? { make: leadState.make, model: leadState.model, year: Number(leadState.year) }
    : null
);
const roofType = normRoof(inboundText) || (category === 'Alfombras WT' ? '' : normRoof(leadState.roof_type));
const needsRoofFitment = category === 'Barras techo';
const detailRequest = /\b(fotos?|foto|detalle|detalles|detalles?\s+completos?|precios?|mas\s+info|más\s+info|mas\s+informacion|más\s+informaci[oó]n|muestrame|mu[eé]strame|desglosa|opciones)\b/i.test(fold(inboundText.replace(/^qr:/i, '')));
const roofSelection = /^QR:ROOF_[A-E]$/i.test(inboundText);
const wtSelection = /^QR:WT_(ROW|UNIV)$/i.test(inboundText);
const cargoType = inferCargoType(inboundText) || flowState.cargo || '';
const bikeMount = inferBikeMount(inboundText) || flowState.mount || '';
const bikeType = inferBikeType(inboundText) || flowState.type || '';

let fitment_query = null;
if (needsRoofFitment && vehicle?.make && vehicle?.model && vehicle?.year && roofType && (roofSelection || detailRequest)) {
  fitment_query = {
    brand: vehicle.make,
    model: vehicle.model,
    year: vehicle.year,
    roof_type: roofType,
  };
}

let wt_query = null;
if (category === 'Alfombras WT' && vehicle?.make && vehicle?.model && vehicle?.year && (wtSelection || detailRequest)) {
  wt_query = {
    brand: 'WeatherTech',
    category: 'alfombras',
    limit: 40,
    wt_type: inferWtType(inboundText) || 'row',
    vehicle,
  };
}

let cargo_query = null;
if (category === 'Canasta/Baúl' && vehicle?.make && vehicle?.model && vehicle?.year && cargoType) {
  cargo_query = {
    brand: 'Thule',
    category: 'Baules y canasta',
    cargo_type: cargoType,
    limit: 80,
    vehicle,
  };
}

let bike_query = null;
if (category === 'Portabici' && vehicle?.make && vehicle?.model && vehicle?.year && bikeMount && bikeType) {
  const barsOk = bikeMount !== 'techo' || /^QR:BIKE_BARS_YES$/i.test(inboundText) || flowState.bars === 'yes';
  if (barsOk) {
    bike_query = {
      brand: 'Thule',
      category: 'Portabicicletas',
      thule_mount: bikeMount,
      thule_bike_type: bikeType,
      limit: 80,
      vehicle,
    };
  }
}

return [{
  json: {
    ...agentOutput,
    active_category: category,
    fitment_query,
    fitment_lookup_attempted: !!fitment_query,
    wt_query,
    wt_lookup_attempted: !!wt_query,
    cargo_query,
    cargo_lookup_attempted: !!cargo_query,
    bike_query,
    bike_lookup_attempted: !!bike_query,
  },
}];
