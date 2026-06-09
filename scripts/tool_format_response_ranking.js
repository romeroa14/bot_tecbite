// Format Response node for Tool - search_attributes_jsonb
// Ranking: exact model > year-range tightness > kit correl > stock

const nodeJson = (...names) => {
  for (const name of names) {
    try { return $(name).first().json; } catch (_) {}
  }
  throw new Error(`Referenced node not found: ${names.join(', ')}`);
};

const input = nodeJson('Build Pattern1', 'Build Pattern');
const rows = $input.all().map((i) => i.json).filter((r) => r && r.product_sku);

if (!input.ok) {
  return [{ json: input }];
}

const fold = (v) => String(v || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const brandF = fold(input.brand);
const modelF = fold(input.model);
const year = Number(input.year);
const roofPatterns = (input.roof_patterns || []).map((p) => fold(p));
const kitCorrel = input.kit_correl;

const normAlnum = (s) => fold(s).replace(/[^a-z0-9]/g, '');

const yearInRange = (rangeRaw) => {
  const m = String(rangeRaw || '').match(/(\d{4})\s*-\s*(\d{4}|)/);
  if (!m) return true;
  const start = parseInt(m[1], 10);
  const end = m[2] ? parseInt(m[2], 10) : 9999;
  return year >= start && year <= end;
};

const yearRangeScore = (rangeRaw) => {
  const m = String(rangeRaw || '').match(/(\d{4})\s*-\s*(\d{4}|)/);
  if (!m) return 40;
  const start = parseInt(m[1], 10);
  const end = m[2] ? parseInt(m[2], 10) : 9999;
  if (year < start || year > end) return -1;
  const width = end - start + 1;
  return Math.max(0, 100 - Math.min(width, 60));
};

const modelMatchScore = (parsed) => {
  const b = fold(parsed.brand);
  const m = fold(parsed.model);
  if (brandF !== b && !b.includes(brandF) && !brandF.includes(b)) return -1;

  const pm = normAlnum(parsed.model);
  const qm = normAlnum(input.model);
  if (pm === qm) return 100;

  const tokens = m.split(/[\s(,\\/-]+/).filter((t) => t.length >= 2);
  if (tokens.some((t) => t === modelF || normAlnum(t) === qm)) return 92;

  const escaped = modelF.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(?:^|[\\s(,/-])${escaped}(?:[\\s(,/-]|$)`);
  if (re.test(m)) return 88;

  if (pm.includes(qm) || qm.includes(pm)) {
    if ((pm.startsWith('ix') || /^i[a-z0-9]{1,2}$/.test(pm)) && !qm.startsWith('i') && qm.length <= 3) return 10;
    if (qm.startsWith('i') && !pm.startsWith('i') && pm.length <= 3) return 10;
    return 42;
  }
  return 0;
};

const parseCaroLine = (line) => {
  const parts = String(line || '').split(',').map((p) => p.trim());
  if (parts.length < 5) return null;
  const edgePart = parts.find((p) => /Edge System:/i.test(p)) || '';
  const evoPart = parts.find((p) => /Evo System:/i.test(p)) || '';
  const edgeSkus = (edgePart.match(/\d{5,7}/g) || []).map((s) => s + (s.endsWith('TH') ? '' : 'TH'));
  const evoSkus = (evoPart.match(/\d{5,7}/g) || []).map((s) => s + (s.endsWith('TH') ? '' : 'TH'));
  return {
    brand: parts[0],
    model: parts[1],
    body: parts[2],
    yearRange: parts[3],
    roofType: parts[4],
    edge_skus: [...new Set(edgeSkus)],
    evo_skus: [...new Set(evoSkus)],
  };
};

const matchesVehicle = (parsed) => {
  if (!parsed) return false;
  if (modelMatchScore(parsed) < 40) return false;
  if (!yearInRange(parsed.yearRange)) return false;
  const roofF = fold(parsed.roofType);
  return roofPatterns.some((rp) => roofF.includes(rp) || rp.includes(roofF));
};

const scoreLine = (parsed) => {
  const ms = modelMatchScore(parsed);
  const ys = yearRangeScore(parsed.yearRange);
  if (ms < 40 || ys < 0) return -1;
  // Peso extra al rango de años (desempate Yaris 5132 vs 5394, etc.)
  return ms + ys * 2.5;
};

const skuCorrelScore = (sku) => {
  if (!kitCorrel) return 0;
  const m = String(sku || '').match(/^(\d)/);
  if (!m) return 0;
  return Number(m[1]) === Number(kitCorrel) ? 25 : -40;
};

const kitMap = new Map();

for (const row of rows) {
  let attrs = {};
  try { attrs = JSON.parse(row.attributes_text || '{}'); } catch (_) {}
  const caroLines = Object.keys(attrs)
    .filter((k) => /^Carro\d+$/i.test(k))
    .map((k) => attrs[k])
    .filter(Boolean);

  const matchedLines = [];
  let bestLineScore = -1;
  for (const line of caroLines) {
    const parsed = parseCaroLine(line);
    if (!matchesVehicle(parsed)) continue;
    const ls = scoreLine(parsed);
    if (ls > bestLineScore) bestLineScore = ls;
    matchedLines.push(parsed);
    parsed.edge_skus.forEach((s) => {});
  }

  if (!matchedLines.length) continue;

  const stockScore = row.stock_status === 'in_stock' ? 30 : row.stock_status === 'out_of_stock' ? 5 : 10;
  const titleScore = /kit/i.test(row.title || '') ? 10 : 0;
  const totalScore = bestLineScore + stockScore + skuCorrelScore(row.product_sku) + titleScore;

  const existing = kitMap.get(row.product_sku);
  if (!existing || totalScore > existing._score) {
    kitMap.set(row.product_sku, {
      sku: row.product_sku,
      title: row.title,
      brand: row.brand,
      category: row.category,
      price: row.price_amount ? `${row.price_amount} ${row.currency || 'USD'}` : 'consultar',
      stock: row.stock_status,
      image_url: row.image_url || null,
      promo: row.promo_text || null,
      kit_correl: kitCorrel,
      roof_label: input.roof_label,
      matched_compat: matchedLines.map((p) => `${p.brand},${p.model},${p.yearRange},${p.roofType}`),
      edge_skus: matchedLines.flatMap((p) => p.edge_skus),
      evo_skus: matchedLines.flatMap((p) => p.evo_skus),
      _score: totalScore,
      _line_score: bestLineScore,
    });
  }
}

const barSkuSet = new Set();
const kits = [...kitMap.values()].sort((a, b) => b._score - a._score);

for (const kit of kits) {
  kit.edge_skus.forEach((s) => barSkuSet.add(s));
  kit.evo_skus.forEach((s) => barSkuSet.add(s));
  delete kit._score;
  delete kit._line_score;
}

if (input.search_mode === 'feet' && kits.length === 0) {
  for (const row of rows) {
    const t = fold(row.title);
    if (t.includes(brandF) && t.includes(modelF)) {
      kits.push({
        sku: row.product_sku,
        title: row.title,
        brand: row.brand,
        category: row.category,
        price: row.price_amount ? `${row.price_amount} ${row.currency || 'USD'}` : 'consultar',
        stock: row.stock_status,
        image_url: row.image_url || null,
        promo: row.promo_text || null,
        product_type: 'feet',
      });
    }
  }
}

if (!kits.length) {
  return [{ json: {
    found: false,
    count: 0,
    message: `Sin match en attributes para ${input.brand} ${input.model} ${input.year} (${input.roof_label}).`,
    query: input,
    results: [],
    bar_skus: [],
  } }];
}

const primary = kits[0];
const ambiguous = kits.length > 1;

return [{ json: {
  found: true,
  count: kits.length,
  source: 'attributes_jsonb',
  search_mode: input.search_mode,
  kit_correl: kitCorrel,
  roof_label: input.roof_label,
  query: input,
  primary_recommendation: primary,
  ambiguous,
  results: kits.slice(0, 5),
  bar_skus: [...barSkuSet].slice(0, 12),
  note: input.search_mode === 'feet'
    ? 'Techo elevado/canal: recomendar pies Thule compatibles; no aplica kit 5/6/7.'
    : ambiguous
      ? 'Varios kits compatibles; usar SOLO results[0] / primary_recommendation salvo que el usuario aclare carrocería.'
      : 'Kit principal en results[0]. Barras solo desde bars[] si el usuario pide detalle.',
} }];
