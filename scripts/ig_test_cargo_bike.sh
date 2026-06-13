#!/usr/bin/env bash
# Canasta/Baúl + Portabici flow tests via Instagram webhook (FLUJO CHATBOT)
# Usage: ./scripts/ig_test_cargo_bike.sh [canasta|baul|bike_roof|bike_hitch|all]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

WEBHOOK_URL="http://n8n.yavingos.com/webhook/instagram-webhook"
PAGE_ID="17841421473742193"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-10}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

send_message() {
  local user_id="$1"
  local text="$2"
  local quick_reply_payload="${3:-}"
  local test_label="$4"

  local message_obj
  if [[ -n "$quick_reply_payload" ]]; then
    message_obj="{\"text\": \"$text\", \"quick_reply\": {\"payload\": \"$quick_reply_payload\"}}"
  else
    message_obj="{\"text\": \"$text\"}"
  fi

  local payload
  payload=$(cat <<EOF
{
  "object": "instagram",
  "entry": [{
    "id": "$PAGE_ID",
    "time": $(date +%s),
    "messaging": [{
      "sender": {"id": "$user_id"},
      "recipient": {"id": "$PAGE_ID"},
      "timestamp": $(date +%s),
      "message": $message_obj
    }]
  }]
}
EOF
)

  echo -e "${CYAN}📤 [$test_label]${NC} $text ${quick_reply_payload:+(QR: $quick_reply_payload)}"
  local response http_code body
  response=$(curl -s -w "\n%{http_code}" -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [[ "$http_code" == "200" ]]; then
    echo -e "  ${GREEN}✅ HTTP $http_code${NC}"
  else
    echo -e "  ${RED}❌ HTTP $http_code — $body${NC}"
  fi
  echo "  ⏳ Waiting ${SLEEP_BETWEEN}s..."
  sleep "$SLEEP_BETWEEN"
}

clean_thread() {
  local user_id="$1"
  echo -e "${YELLOW}Cleaning thread $user_id${NC}"
  DB_HOST="${DB_HOST:-n8n.yavingos.com}" DB_PORT="${DB_PORT:-5433}" DB_NAME="${DB_NAME:-n8ntecbite_db}" \
    DB_USER="${DB_USER:-postgres}" DB_PASS="${DB_PASS:-}" \
    IG_DEFAULT_CONVERSATION_ID="$user_id" "$ROOT_DIR/scripts/ig_clean_thread.sh" "$user_id" 2>/dev/null || true
}

run_canasta() {
  local uid="curl-cargo-canasta-$(date +%s)"
  echo ""
  echo -e "${YELLOW}════════════════ TEST CANASTA — user: $uid ════════════════${NC}"
  clean_thread "$uid"
  send_message "$uid" "Hola" "" "C1"
  send_message "$uid" "Canasta/Baúl" "CAT_CARGO" "C2"
  send_message "$uid" "Toyota RAV4 2022" "" "C3"
  send_message "$uid" "Canasta" "CARGO_CANASTA" "C4"
  echo "$uid"
}

run_baul() {
  local uid="curl-cargo-baul-$(date +%s)"
  echo ""
  echo -e "${YELLOW}════════════════ TEST BAÚL — user: $uid ════════════════${NC}"
  clean_thread "$uid"
  send_message "$uid" "Hola" "" "B1"
  send_message "$uid" "Canasta/Baúl" "CAT_CARGO" "B2"
  send_message "$uid" "Toyota RAV4 2022" "" "B3"
  send_message "$uid" "Baúl" "CARGO_BAUL" "B4"
  echo "$uid"
}

run_bike_roof() {
  local uid="curl-bike-roof-$(date +%s)"
  echo ""
  echo -e "${YELLOW}════════════════ TEST PORTABICI TECHO — user: $uid ════════════════${NC}"
  clean_thread "$uid"
  send_message "$uid" "Hola" "" "P1"
  send_message "$uid" "Portabici" "CAT_BIKE" "P2"
  send_message "$uid" "Toyota RAV4 2022" "" "P3"
  send_message "$uid" "Techo" "BIKE_M_ROOF" "P4"
  send_message "$uid" "MTB" "BIKE_T_MTB" "P5"
  send_message "$uid" "Sí, tengo barras" "BIKE_BARS_YES" "P6"
  echo "$uid"
}

run_bike_hitch() {
  local uid="curl-bike-hitch-$(date +%s)"
  echo ""
  echo -e "${YELLOW}════════════════ TEST PORTABICI REMOLQUE ELÉCTRICA — user: $uid ════════════════${NC}"
  clean_thread "$uid"
  send_message "$uid" "Hola" "" "H1"
  send_message "$uid" "Portabici" "CAT_BIKE" "H2"
  send_message "$uid" "Toyota RAV4 2022" "" "H3"
  send_message "$uid" "Remolque" "BIKE_M_HITCH" "H4"
  send_message "$uid" "Eléctrica" "BIKE_T_ELEC" "H5"
  echo "$uid"
}

USERS=()
case "${1:-all}" in
  canasta)
    uid="$(run_canasta | tail -1)"
    USERS+=("$uid")
    ;;
  baul)
    uid="$(run_baul | tail -1)"
    USERS+=("$uid")
    ;;
  bike_roof)
    uid="$(run_bike_roof | tail -1)"
    USERS+=("$uid")
    ;;
  bike_hitch)
    uid="$(run_bike_hitch | tail -1)"
    USERS+=("$uid")
    ;;
  all|*)
    USERS+=("$(run_canasta | tail -1)")
    USERS+=("$(run_baul | tail -1)")
    USERS+=("$(run_bike_roof | tail -1)")
    USERS+=("$(run_bike_hitch | tail -1)")
    ;;
esac

echo ""
echo -e "${YELLOW}Done. Test user IDs:${NC}"
for u in "${USERS[@]}"; do
  echo "  $u"
done
echo ""
echo -e "${CYAN}Run: python3 scripts/ig_fetch_test_responses.py ${USERS[*]}${NC}"
