#!/usr/bin/env bash
# Discover Telegram chat_id after adding the bot to your group and sending any message.
# Usage (from repo root):
#   ./scripts/telegram_ops_get_chat_id.sh
# Or: TELEGRAM_OPS_BOT_TOKEN=xxx ./scripts/telegram_ops_get_chat_id.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

TOKEN="${TELEGRAM_OPS_BOT_TOKEN:-}"
TOKEN="$(printf '%s' "$TOKEN" | tr -d '\r\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

if [[ -z "$TOKEN" ]]; then
  echo "Falta TELEGRAM_OPS_BOT_TOKEN."
  echo "Agrégalo en ${ROOT}/.env o exporta la variable en tu terminal."
  exit 1
fi

if [[ ! "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
  echo "El token no tiene formato válido de BotFather (esperado: 123456789:ABCdef...)."
  echo "Revisa que no tenga comillas extra, espacios o saltos de línea."
  exit 1
fi

echo "Probando token (${#TOKEN} caracteres, sin mostrar valor)..."
ME=$(curl -s "https://api.telegram.org/bot${TOKEN}/getMe")
if ! python3 -c "import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" <<<"$ME"; then
  echo "Telegram rechazó el token (401 Unauthorized)."
  echo "Acciones:"
  echo "  1. Abre @BotFather → /mybots → tu bot → API Token → Copy"
  echo "  2. Pega SOLO el token en ${ROOT}/.env como TELEGRAM_OPS_BOT_TOKEN=..."
  echo "  3. Si lo compartiste o dudas, usa Revoke en BotFather y genera uno nuevo"
  python3 -c "import json,sys; print(json.load(sys.stdin).get('description',''))" <<<"$ME" 2>/dev/null || true
  exit 1
fi

BOT_NAME=$(python3 -c "import json,sys; print(json.load(sys.stdin)['result'].get('username','?'))" <<<"$ME")
echo "Token OK — bot @${BOT_NAME}"
echo ""
echo "Buscando chat_id (escribe un mensaje en el grupo con el bot añadido)..."
echo ""

curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if not data.get('ok'):
    print('API error:', data)
    sys.exit(1)
rows = data.get('result', [])[-15:]
if not rows:
    print('Sin mensajes aún.')
    print('1) Añade el bot al grupo')
    print('2) Escribe hola en el grupo')
    print('3) Vuelve a ejecutar este script')
    sys.exit(0)
for u in rows:
    chat = (u.get('message') or {}).get('chat') or (u.get('my_chat_member') or {}).get('chat')
    if not chat:
        continue
    title = chat.get('title') or chat.get('first_name') or '?'
    print(f\"chat_id={chat['id']}  type={chat.get('type')}  title={title}\")
print()
print('Usa el chat_id del GRUPO (número negativo) en TELEGRAM_OPS_CHAT_IDS')
"
