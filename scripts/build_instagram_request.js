const items = $input.all();
const fallbackUserId = (() => {
  try { return $('Filter & Normalize2').item.json.user_id; } catch (_) { return ''; }
})();

return items.map((item) => {
  const msg = item.json || {};
  const userId = msg.user_id || fallbackUserId;
  const recipient = { id: userId };
  let body;

  if (msg.type === 'image' && msg.image_url) {
    body = JSON.stringify({
      recipient,
      message: {
        attachment: {
          type: 'image',
          payload: { url: msg.image_url, is_reusable: true },
        },
      },
    });
  } else if (msg.type === 'button_template' && Array.isArray(msg.buttons) && msg.buttons.length) {
    body = JSON.stringify({
      recipient,
      message: {
        attachment: {
          type: 'template',
          payload: {
            template_type: 'button',
            text: String(msg.content || 'Elige:').substring(0, 640),
            buttons: msg.buttons.slice(0, 3).map((b) => ({
              type: 'web_url',
              title: String(b.title || 'Abrir WhatsApp').substring(0, 20),
              url: String(b.url || '').substring(0, 1000),
            })),
          },
        },
      },
    });
  } else if (msg.type === 'text_with_quick_replies' && msg.options && msg.options.length > 0) {
    const qr = [];
    const max = Math.min(msg.options.length, 13);
    for (let i = 0; i < max; i++) {
      qr.push({
        content_type: 'text',
        title: String(msg.options[i]).substring(0, 20),
        payload: (msg.payloads && msg.payloads[i])
          ? String(msg.payloads[i]).substring(0, 1000)
          : `OPTION_${i}`,
      });
    }
    body = JSON.stringify({
      recipient,
      message: {
        text: String(msg.content || 'Elige:').substring(0, 2000),
        quick_replies: qr,
      },
    });
  } else {
    body = JSON.stringify({
      recipient,
      message: { text: String(msg.content || msg.text || '¡Hola!').substring(0, 1000) },
    });
  }

  return { json: { body, user_id: userId, message_type: msg.type || 'text' } };
});
