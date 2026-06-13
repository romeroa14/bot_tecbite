// Shared helpers for WeatherTech vehicle product filtering (used in prepare + format enforcers)

const inferProductCategory = (text, leadCategory = '') => {
  const f = String(text || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
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

const normalizeComparable = (value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/g, '');

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
    const folded = title.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
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
    if (out.length >= 4) break;
  }
  out.sort((a, b) => {
    const rank = (s) => (s === 'in_stock' ? 0 : s === 'out_of_stock' ? 1 : 2);
    return rank(a?.stock) - rank(b?.stock);
  });
  return out.slice(0, 3);
};

const inferWtType = (inboundText) => {
  const upper = String(inboundText || '').toUpperCase();
  if (upper.includes('QR:WT_UNIV')) return 'univ';
  if (upper.includes('QR:WT_ROW')) return 'row';
  return '';
};
