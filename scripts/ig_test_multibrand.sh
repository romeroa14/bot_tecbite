#!/usr/bin/env bash
# Multi-brand bars fitment test via Instagram webhook
# Usage: ./scripts/ig_test_multibrand.sh [1|2|3|4|all]

set -euo pipefail

WEBHOOK_URL="http://n8n.yavingos.com/webhook/instagram-webhook"
PAGE_ID="17841421473742193"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-8}"

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
    DB_USER="${DB_USER:-postgres}" DB_PASS="${DB_PASS:-Tecbite20\$}" \
    IG_DEFAULT_CONVERSATION_ID="$user_id" /var/www/html/tecbite/scripts/ig_clean_thread.sh "$user_id" 2>/dev/null || true
}

run_case() {
  local num="$1"
  local user_id="$2"
  local vehicle="$3"
  local roof_qr="$4"
  local roof_label="$5"
  local title="$6"

  echo ""
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}  TEST $num: $title${NC}"
  echo -e "${YELLOW}  User: $user_id | Vehicle: $vehicle | Roof: $roof_label${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"

  clean_thread "$user_id"
  send_message "$user_id" "Hola" "" "T${num}-1"
  send_message "$user_id" "Barras techo" "CAT_BARS" "T${num}-2"
  send_message "$user_id" "$vehicle" "" "T${num}-3"
  send_message "$user_id" "$roof_label" "$roof_qr" "T${num}-4"
}

# Test IDs (unique per case)
TEST1_USER="curl-bmw-x3-$(date +%s)"
TEST2_USER="curl-nissan-fr-$(date +%s)"
TEST3_USER="curl-hyundai-tuc-$(date +%s)"
TEST4_USER="curl-honda-crv-$(date +%s)"

case "${1:-all}" in
  1)
    run_case 1 "$TEST1_USER" "BMW X3 2018" "ROOF_B" "Riel integrado" "BMW X3 2018 — Flush Rails (limpio)"
    ;;
  2)
    run_case 2 "$TEST2_USER" "Nissan Frontier 2022" "ROOF_D" "Techo liso" "Nissan Frontier 2022 — Normal Roof (limpio)"
    ;;
  3)
    run_case 3 "$TEST3_USER" "Hyundai Tucson 2019" "ROOF_B" "Riel integrado" "Hyundai Tucson 2019 — ambiguo (Flush vs Normal)"
    ;;
  4)
    run_case 4 "$TEST4_USER" "Honda CR-V 2017" "ROOF_D" "Techo liso" "Honda CR-V 2017 — ambiguo (Normal vs flush+fixpoint)"
    ;;
  all|*)
    run_case 1 "$TEST1_USER" "BMW X3 2018" "ROOF_B" "Riel integrado" "BMW X3 2018 — Flush Rails (limpio)"
    run_case 2 "$TEST2_USER" "Nissan Frontier 2022" "ROOF_D" "Techo liso" "Nissan Frontier 2022 — Normal Roof (limpio)"
    run_case 3 "$TEST3_USER" "Hyundai Tucson 2019" "ROOF_B" "Riel integrado" "Hyundai Tucson 2019 — ambiguo"
    run_case 4 "$TEST4_USER" "Honda CR-V 2017" "ROOF_D" "Techo liso" "Honda CR-V 2017 — ambiguo"
    ;;
esac

echo ""
echo -e "${YELLOW}Done. Check n8n executions and instagram_conversation_event for responses.${NC}"
echo "Test user IDs used:"
echo "  1: $TEST1_USER"
echo "  2: $TEST2_USER"
echo "  3: $TEST3_USER"
echo "  4: $TEST4_USER"
