// Notify Telegram Ops — push alerts to marketing group (after Save Lead State)
const token = $env.TELEGRAM_OPS_BOT_TOKEN || '';
const chatIdsRaw = $env.TELEGRAM_OPS_CHAT_IDS || '';
const chatIds = chatIdsRaw.split(',').map((s) => s.trim()).filter(Boolean);

const curr = $('Parse State Updates').first().json || {};
const prev = (() => {
  try { return $('Get Lead State').first().json || {}; } catch (_) { return {}; }
})();

const inbound = String(curr.inbound_payload?.text || '').trim();
const inboundUpper = inbound.toUpperCase();
const conversationId = String(curr.conversation_id || curr.user_id || '').trim();
const messageId = String(curr.message_id || '').trim();

if (!token || !chatIds.length || !conversationId) {
  return [{ json: { telegram_skipped: true, reason: 'missing_config_or_conversation' } }];
}

const payloadBase = {
  conversation_id: conversationId,
  message_id: messageId,
  user_id: curr.user_id,
  make: curr.make,
  model: curr.model,
  year: curr.year,
  category: curr.category,
  stage: curr.stage,
  roof_type: curr.roof_type || null,
  inbound_text: inbound,
};

const notifications = [];

const isHandoff = curr.stage === 'handoff'
  || inboundUpper.includes('QR:WHATSAPP')
  || inboundUpper.includes('QR:ADV_');

if (isHandoff) {
  notifications.push({ type: 'handoff', payload: payloadBase });
}

const slotsBecameReady = curr.slots_complete === true && prev.slots_complete !== true;
if (slotsBecameReady) {
  notifications.push({ type: 'lead_ready', payload: payloadBase });
}

const prevCat = String(prev.category || '').trim();
const currCat = String(curr.category || '').trim();
if (prevCat && currCat && prevCat !== currCat) {
  notifications.push({
    type: 'category_switch',
    payload: { ...payloadBase, prev_category: prevCat },
  });
}

const prevHadVehicle = !!(prev.make && prev.model && prev.year);
const currHasVehicle = !!(curr.make && curr.model && curr.year);
if (currHasVehicle && !prevHadVehicle) {
  notifications.push({ type: 'new_vehicle', payload: payloadBase });
}

if (!notifications.length) {
  return [{ json: { telegram_skipped: true, reason: 'no_trigger' } }];
}

const escapeMd = (v) => String(v || '').replace(/([\\_*[\\]()])/g, '\\$1');

const formatPush = (type, data) => {
  const veh = [data.make, data.model, data.year].filter(Boolean).join(' ') || '—';
  const cid = escapeMd(String(data.conversation_id || '').slice(0, 18));
  const cat = escapeMd(data.category || '—');
  if (type === 'handoff') {
    return `📞 *Handoff — asesor humano*\n\nCliente: \`${cid}\`\nVehículo: *${escapeMd(veh)}*\nProducto: ${cat}`;
  }
  if (type === 'lead_ready') {
    const roof = data.roof_type ? `\nTecho: ${escapeMd(data.roof_type)}` : '';
    return `✅ *Lead listo para cotizar*\n\nCliente: \`${cid}\`\nVehículo: *${escapeMd(veh)}*\nProducto: ${cat}${roof}`;
  }
  if (type === 'category_switch') {
    return `🔀 *Cambio de producto*\n\nCliente: \`${cid}\`\nVehículo: *${escapeMd(veh)}*\nAntes: ${escapeMd(data.prev_category)}\nAhora: *${cat}*`;
  }
  if (type === 'new_vehicle') {
    return `🆕 *Nuevo vehículo en hilo*\n\nCliente: \`${cid}\`\nVehículo: *${escapeMd(veh)}*\nProducto: ${cat}`;
  }
  return `ℹ️ Ops: ${cid}`;
};

const results = [];

for (const note of notifications) {
  let logged = false;
  try {
    const ins = await $helpers.httpRequest({
      method: 'POST',
      url: `https://api.telegram.org/bot${token}/sendMessage`,
      body: {
        chat_id: chatIds[0],
        text: formatPush(note.type, note.payload).slice(0, 4000),
        parse_mode: 'Markdown',
        disable_web_page_preview: true,
      },
      json: true,
    });
    logged = !!ins?.ok;
  } catch (_) {}

  for (const chatId of chatIds.slice(1)) {
    try {
      await $helpers.httpRequest({
        method: 'POST',
        url: `https://api.telegram.org/bot${token}/sendMessage`,
        body: {
          chat_id: chatId,
          text: formatPush(note.type, note.payload).slice(0, 4000),
          parse_mode: 'Markdown',
          disable_web_page_preview: true,
        },
        json: true,
      });
    } catch (_) {}
  }

  results.push({ type: note.type, sent: logged });
}

return [{ json: { telegram_notified: true, results } }];
