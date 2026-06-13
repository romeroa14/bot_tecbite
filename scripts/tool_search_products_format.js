// Thule cargo + portabici filters (FLUJO CHATBOT)
const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

const isCargoAccessory = (title, category) => {
  const t = fold(`${title} ${category}`);
  return /lid cover|box light|acu tight|knob|strap kit|rail mount|eye bolt|crossbar kit|cargo box kit|railing kit|platform ball mount|arcos platform|backspace|gopack duffel|vista hitch bag|vista folding|caprock rail|caprock roof platform|load\s*net|stretch cargo|\boutbound\b|extension xt/i.test(t);
};

const filterCargoProducts = (results, cargoType) => {
  const dedup = new Set();
  const out = [];
  for (const row of results || []) {
    const title = String(row?.title || '');
    const category = String(row?.category || '');
    const titleF = fold(title);
    if (isCargoAccessory(title, category)) continue;
    if (cargoType === 'canasta') {
      if (!(/canyon|\bbasket\b/i.test(titleF))) continue;
    } else if (cargoType === 'baul') {
      if (!(/force\s*3|motion\s*3|motion\s*xt|\bbox\b/i.test(titleF))) continue;
      if (/canyon/i.test(titleF)) continue;
    }
    const sku = String(row?.sku || row?.product_sku || '').trim().toUpperCase();
    if (sku && dedup.has(sku)) continue;
    if (sku) dedup.add(sku);
    out.push(row);
  }
  const rank = (s) => (s === 'in_stock' ? 0 : s === 'out_of_stock' ? 1 : 2);
  out.sort((a, b) => {
    const pa = Number(String(a?.price_amount || a?.price || '').match(/[\d.]+/)?.[0] || 0);
    const pb = Number(String(b?.price_amount || b?.price || '').match(/[\d.]+/)?.[0] || 0);
    return rank(a?.stock) - rank(b?.stock) || pa - pb;
  });
  return out.slice(0, 6);
};

const BIKE_HITCH_ELECTRIC = [/t2\s*pro\s*xtr/i, /\bverse\b/i];
const BIKE_HITCH_STANDARD = [/apex\s*xt/i, /helium\s*pro/i, /outpace/i, /helium\s*platform/i, /t2\s*pro\s*xtr/i, /\bverse\b/i, /revert/i];

const filterBikeProducts = (results, mount, bikeType) => {
  const dedup = new Set();
  const out = [];
  for (const row of results || []) {
    const title = String(row?.title || '');
    const category = String(row?.category || '');
    const f = fold(`${title} ${category}`);
    if (/adapter|holder|wheel tray|repair holder|end cap|transport wheel|add-on|thru-axle|snug-tite|alternative bike|adjustable bike stand|bike stand|spare me|low rider|locking low|rueda|wheel\s*strap|cradle\s*strap|front wheel holder/i.test(f)) {
      if (mount !== 'acc') continue;
    }
    if (mount === 'techo' && !/portabicicletas > techo/i.test(fold(category))) continue;
    if (mount === 'joroba' && !/joroba/i.test(f)) continue;
    if (mount === 'pickup' && !(/pick\s*up|gate mate|bed rider|insta-gater/i.test(f))) continue;
    if (mount === 'bola' && !(/portabicicletas > bola|\bxpress\b/i.test(f))) continue;
    if (mount === 'hitch' && !(/remolque|hitch/i.test(f))) continue;
    if (mount === 'acc' && !(/accesorios|roundtrip|transport wheel|front wheel/i.test(f))) continue;
    if (mount === 'hitch' && bikeType === 'electric') {
      if (!BIKE_HITCH_ELECTRIC.some((r) => r.test(title))) continue;
    } else if (mount === 'hitch' && bikeType) {
      if (!BIKE_HITCH_STANDARD.some((r) => r.test(title))) continue;
    }
    const sku = String(row?.sku || row?.product_sku || '').trim().toUpperCase();
    if (sku && dedup.has(sku)) continue;
    if (sku) dedup.add(sku);
    out.push(row);
  }
  const rank = (s) => (s === 'in_stock' ? 0 : s === 'out_of_stock' ? 1 : 2);
  out.sort((a, b) => rank(a?.stock) - rank(b?.stock));
  return out.slice(0, 6);
};

const nodeJson = (...names) => {
  for (const name of names) {
    try { return $(name).first().json; } catch (_) {}
  }
  throw new Error(`Referenced node not found: ${names.join(', ')}`);
};

const rows = $input.all().map((i) => i.json).filter((r) => r && r.product_sku);
const input = nodeJson('Normalize Input1', 'Normalize Input');

let filtered = rows;
if (input.cargo_type) {
  filtered = filterCargoProducts(rows, input.cargo_type);
} else if (input.thule_mount) {
  filtered = filterBikeProducts(rows, input.thule_mount, input.thule_bike_type || '');
}

const validRows = filtered.filter((r) => r && r.product_sku);
const limited = validRows.slice(0, input.limit || 10);

if (!limited.length) {
  return [{ json: {
    found: false,
    count: 0,
    total_found: 0,
    message: `No hay productos activos para brand='${input.brand}' category='${input.category}' cargo='${input.cargo_type || ''}' mount='${input.thule_mount || ''}'.`,
    query: input,
    results: [],
  } }];
}

return [{ json: {
  found: true,
  count: limited.length,
  total_found: validRows.length,
  query: input,
  results: limited.map((r) => ({
    sku: r.product_sku,
    title: r.title,
    brand: r.brand,
    category: r.category,
    price: r.price_amount ? `${r.price_amount} ${r.currency || 'USD'}` : 'consultar',
    stock: r.stock_status,
    image_url: r.image_url || null,
    promo: r.promo_text || null,
  })),
} }];
