const raw = $input.first().json || {};
const data = (raw.query && typeof raw.query === 'object' && !Array.isArray(raw.query)) ? raw.query : raw;
const vehicle = (data.vehicle && typeof data.vehicle === 'object') ? data.vehicle : {};

const brand = String(data.brand || raw.brand || '').trim();
let category = String(data.category || raw.category || '').trim();
const limitRaw = parseInt(data.limit || raw.limit, 10);
const limit = Math.max(1, Math.min(Number.isFinite(limitRaw) ? limitRaw : 10, 100));
const vehicle_make = String(vehicle.make || data.vehicle_make || '').trim();
const vehicle_model = String(vehicle.model || data.vehicle_model || '').trim();
const vehicle_year = Number(vehicle.year || data.vehicle_year) || null;
const cargo_type = String(data.cargo_type || raw.cargo_type || '').trim();
const thule_mount = String(data.thule_mount || raw.thule_mount || '').trim();
const thule_bike_type = String(data.thule_bike_type || raw.thule_bike_type || '').trim();

const mountNeedle = (mount) => {
  if (mount === 'techo') return 'Portabicicletas > Techo';
  if (mount === 'joroba') return 'Portabicicletas > Joroba';
  if (mount === 'pickup') return 'Portabicicletas > Pick Up';
  if (mount === 'bola') return 'Portabicicletas > Bola';
  if (mount === 'hitch') return 'Portabicicletas > Remolque';
  return '';
};

if (thule_mount && !category.includes('Portabicicletas')) {
  const needle = mountNeedle(thule_mount);
  if (needle) category = needle;
}

return [{ json: {
  brand,
  category,
  limit,
  vehicle_make,
  vehicle_model,
  vehicle_year,
  cargo_type,
  thule_mount,
  thule_bike_type,
} }];
