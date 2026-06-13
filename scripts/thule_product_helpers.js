// Shared Thule cargo + portabici catalog filters (FLUJO CHATBOT doc)

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');

const inferCargoType = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:CARGO_CANASTA') || upper.includes('QR:CARGO_BASKET')) return 'canasta';
  if (upper.includes('QR:CARGO_BAUL') || upper.includes('QR:CARGO_BOX')) return 'baul';
  const f = fold(text);
  if (/\bcanasta\b/.test(f) && !/\bbaul\b/.test(f)) return 'canasta';
  if (/\bbaul\b/.test(f) || /\bbaúl\b/.test(f) || /\bbox\b/.test(f)) return 'baul';
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
  const f = fold(text);
  if (/electri/.test(f) || /\be\s*bike\b/.test(f)) return 'electric';
  if (/\bmtb\b/.test(f) || /monta[nñ]a/.test(f)) return 'mtb';
  if (/\bruta\b/.test(f) || /carretera/.test(f)) return 'ruta';
  return '';
};

const inferBikeBarsAnswer = (text) => {
  const upper = String(text || '').toUpperCase();
  if (upper.includes('QR:BIKE_BARS_YES')) return 'yes';
  if (upper.includes('QR:BIKE_BARS_NO')) return 'no';
  return '';
};

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
  out.sort((a, b) => rank(a?.stock) - rank(b?.stock) || Number(a?.price?.match?.(/[\d.]+/)?.[0] || a?.price_amount || 0) - Number(b?.price?.match?.(/[\d.]+/)?.[0] || b?.price_amount || 0));
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

const mountCategoryNeedle = (mount) => {
  if (mount === 'techo') return 'Portabicicletas > Techo';
  if (mount === 'joroba') return 'Portabicicletas > Joroba';
  if (mount === 'pickup') return 'Portabicicletas > Pick Up';
  if (mount === 'bola') return 'Portabicicletas > Bola';
  if (mount === 'hitch') return 'Portabicicletas > Remolque';
  if (mount === 'acc') return 'Portabicicletas';
  return 'Portabicicletas';
};
