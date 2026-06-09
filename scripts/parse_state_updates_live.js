const agentOutput = $input.first().json || {};
const steps = Array.isArray(agentOutput.intermediateSteps) ? agentOutput.intermediateSteps : [];

const prevState = (() => {
  try {
    return $('Get Lead State').item.json || {};
  } catch (_) {
    return {};
  }
})();

let inboundText = '';
let outboundText = String(agentOutput.output || agentOutput.text || '').trim();
let user_id = '';
let message_id = '';
try {
  inboundText = String($('Filter & Normalize2').item.json.message_text || '').trim();
  user_id = $('Filter & Normalize2').item.json.user_id || '';
  message_id = $('Filter & Normalize2').item.json.message_id || '';
} catch (_) {}

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const cleanString = (value) => {
  if (value === undefined) return undefined;
  if (value === null) return null;
  const str = String(value).trim();
  if (!str || str.toLowerCase() === 'null' || str.toLowerCase() === 'undefined') return null;
  return str;
};
const cleanYear = (value) => {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const match = String(value).match(/\b(19|20)\d{2}\b/);
  return match ? Number(match[0]) : null;
};
const normRoof = (value) => {
  if (value === undefined) return undefined;
  if (value === null) return null;
  const rawText = String(value).trim();
  const raw = rawText.toUpperCase();
  const folded = fold(rawText);
  if (!raw || raw === 'NULL' || raw === 'UNDEFINED') return null;
  if (raw.startsWith('QR:ROOF_')) return raw.replace('QR:', '');
  if (raw.startsWith('ROOF_')) return raw;
  if (/^[A-E]$/.test(raw)) return `ROOF_${raw}`;
  const match = raw.match(/\[USER_ROOF:([A-E])\]/);
  if (match) return `ROOF_${match[1]}`;
  if (/\briel\s+elevad[oa]\b|\braised\b/.test(folded)) return 'ROOF_A';
  if (/\briel\s+integrad[oa]\b|\briel\s+alinead[oa]\b|\bflush\s+rail/.test(folded)) return 'ROOF_B';
  if (/\bpunto\s+de\s+fijacion\b|\bfixed\s+point/.test(folded)) return 'ROOF_C';
  if (/\btecho\s+liso\b|\bnormal\s+roof/.test(folded)) return 'ROOF_D';
  if (/\bcanal\s+de\s+agua\b|\bgutter/.test(folded)) return 'ROOF_E';
  return null;
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

const normalizeComparable = (value) => fold(value).replace(/[^a-z0-9]/g, '');

const extractStateUpdate = (text) => {
  const lines = String(text || '').split('\n').map((line) => line.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    if (!lines[i].startsWith('[STATE_UPDATE]')) continue;
    const rawJson = lines[i].replace(/^\[STATE_UPDATE\]\s*/, '');
    try {
      return JSON.parse(rawJson);
    } catch (_) {
      return null;
    }
  }
  return null;
};

const stateUpdate = extractStateUpdate(outboundText) || {};
outboundText = String(outboundText)
  .split('\n')
  .filter((line) => !line.trim().startsWith('[STATE_UPDATE]'))
  .join('\n')
  .replace(/\n{3,}/g, '\n\n')
  .trim();

const inboundVehicle = extractVehicle(inboundText);
const prevVehicle = {
  make: cleanString(prevState.make ?? null),
  model: cleanString(prevState.model ?? null),
  year: cleanYear(prevState.year ?? null),
};
const vehicleChanged = !!(
  inboundVehicle &&
  (
    normalizeComparable(inboundVehicle.make) !== normalizeComparable(prevVehicle.make) ||
    normalizeComparable(inboundVehicle.model) !== normalizeComparable(prevVehicle.model) ||
    inboundVehicle.year !== prevVehicle.year
  )
);
const hardResetRequested = /\b(otra\s+cotizacion|otra\s+cotización|nuevo\s+vehiculo|nuevo\s+vehículo|cambiar\s+de\s+vehiculo|cambiar\s+de\s+vehículo|empezar\s+de\s+nuevo|empezar\s+de\s+cero)\b/i.test(fold(inboundText));
const newVehicleContext = !!stateUpdate.new_vehicle_context || vehicleChanged || hardResetRequested;

let make = newVehicleContext ? null : prevVehicle.make;
let model = newVehicleContext ? null : prevVehicle.model;
let year = newVehicleContext ? null : prevVehicle.year;
let roof_type = newVehicleContext ? null : normRoof(prevState.roof_type ?? null);
let category = cleanString(prevState.category ?? null);
let stage = cleanString(prevState.stage) || 'greeting';

if (inboundVehicle) {
  make = inboundVehicle.make;
  model = inboundVehicle.model;
  year = inboundVehicle.year;
}

const applyToolInput = (toolInput) => {
  if (!toolInput || typeof toolInput !== 'object') return;
  const brand = cleanString(toolInput.brand ?? toolInput.make);
  const modelValue = cleanString(toolInput.model);
  const yearValue = cleanYear(toolInput.year);
  const categoryValue = cleanString(toolInput.category);
  const roofValue = normRoof(toolInput.roof_type ?? toolInput.roof ?? toolInput.roof_code);
  if (brand && !make) make = brand;
  if (modelValue && !model) model = modelValue;
  if (yearValue && !year) year = yearValue;
  if (categoryValue && !category) category = categoryValue;
  if (roofValue && !roof_type) roof_type = roofValue;
};

for (const step of steps) {
  applyToolInput(step?.action?.toolInput);
  applyToolInput(step?.action?.input);
  applyToolInput(step?.action);
}

const stateMake = cleanString(stateUpdate.make);
const stateModel = cleanString(stateUpdate.model);
const stateYear = cleanYear(stateUpdate.year);
const stateCategory = cleanString(stateUpdate.category);
const stateRoof = normRoof(stateUpdate.roof_type);

if (stateMake !== undefined) make = stateMake;
if (stateModel !== undefined) model = stateModel;
if (stateYear !== undefined) year = stateYear;
if (stateCategory !== undefined) category = stateCategory;
if (stateRoof !== undefined) roof_type = stateRoof;

const inboundUpper = inboundText.toUpperCase();
const inboundFold = fold(inboundText);

const inferredCategory = (() => {
  if (inboundUpper.includes('QR:CAT_BARS')) return 'Barras techo';
  if (inboundUpper.includes('QR:CAT_CARGO')) return 'Canasta/Baúl';
  if (inboundUpper.includes('QR:CAT_BIKE')) return 'Portabici';
  if (inboundUpper.includes('QR:CAT_WT') || inboundUpper.includes('QR:WT_ROW') || inboundUpper.includes('QR:WT_UNIV')) return 'Alfombras WT';
  if (/\bbarras?\b/.test(inboundFold) || /roof\s*rack/.test(inboundFold) || /portaequipaje/.test(inboundFold)) return 'Barras techo';
  if (/\bcanasta\b/.test(inboundFold) || /\bbaul\b/.test(inboundFold) || /\bbaúl\b/.test(inboundFold)) return 'Canasta/Baúl';
  if (/\bportabici\b/.test(inboundFold) || /\bbici\b/.test(inboundFold)) return 'Portabici';
  if (/\balfombra\b/.test(inboundFold) || /weathertech/.test(inboundFold) || /floorliner/.test(inboundFold)) return 'Alfombras WT';
  return null;
})();
if (inferredCategory) category = inferredCategory;

const inboundRoof = normRoof(inboundText);
if (inboundRoof) roof_type = inboundRoof;

const outputUpper = outboundText.toUpperCase();
const needsRoof = ['Barras techo', 'Canasta/Baúl'].includes(category || '');

if (outputUpper.includes('[ROOF_MENU]')) {
  stage = 'collect_roof';
} else if (outputUpper.includes('[WT_MENU]') || outputUpper.includes('[MAIN_MENU]')) {
  stage = 'collect_category';
} else if (outboundText.includes('Dave') || outboundText.includes('Eduardo') || outputUpper.includes('WHATSAPP')) {
  stage = 'handoff';
} else if (!category) {
  stage = 'collect_category';
} else if (!make) {
  stage = 'collect_make';
} else if (!model) {
  stage = 'collect_model';
} else if (!year) {
  stage = 'collect_year';
} else if (needsRoof && !roof_type) {
  stage = 'collect_roof';
} else {
  stage = 'recommend';
}

const slots_complete = !!(category && make && model && year && (!needsRoof || roof_type));

return [{
  json: {
    conversation_id: user_id,
    user_id,
    make,
    model,
    year,
    roof_type,
    category,
    stage,
    slots_complete,
    reset_vehicle_context: newVehicleContext,
    message_id,
    inbound_payload: {
      text: inboundText,
      state_update: stateUpdate || null,
      inbound_vehicle: inboundVehicle,
    },
    outbound_payload: {
      text: outboundText,
    },
  },
}];
