#!/usr/bin/env bash
# Pruebas curl para Tecbite AI Agent v2 (tool-based)
# Uso: ./test_v2_curl.sh [test_number]
#   ./test_v2_curl.sh       -> corre todos
#   ./test_v2_curl.sh 1     -> corre solo el caso 1

set -e

WEBHOOK_URL="${WEBHOOK_URL:-https://n8n.yavingos.com/webhook/instagram-webhook}"
USER_ID="${USER_ID:-987654321}"
PAGE_ID="${PAGE_ID:-123456789}"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

run_test() {
  local n="$1" name="$2" payload="$3"
  echo
  echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}TEST $n: $name${NC}"
  echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}Payload:${NC}"
  echo "$payload" | jq -C . 2>/dev/null || echo "$payload"
  echo
  echo -e "${YELLOW}POST → $WEBHOOK_URL${NC}"
  local start ms
  start=$(date +%s%3N)
  local http_code
  http_code=$(curl -s -o /tmp/v2_resp_$n.txt -w "%{http_code}" -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$payload")
  ms=$(( $(date +%s%3N) - start ))
  if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✓ HTTP $http_code (${ms}ms)${NC}"
  else
    echo -e "${RED}✗ HTTP $http_code (${ms}ms)${NC}"
  fi
  echo -e "${YELLOW}Response body:${NC}"
  cat /tmp/v2_resp_$n.txt | jq -C . 2>/dev/null || cat /tmp/v2_resp_$n.txt
  echo
  echo -e "${YELLOW}→ Revisa la ejecución en n8n: ${NC}https://n8n.yavingos.com/executions"
}

build_payload() {
  local text="$1" ref="$2" ad_id="$3"
  local referral=""
  if [ -n "$ref" ]; then
    referral=",\"referral\":{\"ref\":\"$ref\",\"ad_id\":\"$ad_id\",\"source\":\"ADS\"}"
  fi
  cat <<EOF
{
  "object": "page",
  "entry": [{
    "id": "$PAGE_ID",
    "time": $(date +%s),
    "messaging": [{
      "sender": {"id": "$USER_ID"},
      "recipient": {"id": "$PAGE_ID"},
      "timestamp": $(date +%s)$referral,
      "message": {
        "mid": "mid.test.$(date +%s%N)",
        "text": "$text"
      }
    }]
  }]
}
EOF
}

# ───────── Casos de prueba ─────────

test_1() {
  run_test 1 "Mitsubishi Montero Sport 2023 (caso que fallaba en v1)" \
    "$(build_payload 'Hola para mitsubishi montero sport 2023 tienen')"
}

test_2() {
  run_test 2 "CURT campaña real + 'precio' (con ad_ref)" \
    "$(build_payload 'precio' 'CURT-HITCH-SYSTEM-199' 'CURT-AD-001')"
}

test_3() {
  run_test 3 "Pregunta descriptiva (vector search)" \
    "$(build_payload 'el portabicicletas thule sirve para bici electrica?')"
}

test_4() {
  run_test 4 "Stock genérico sin vehículo" \
    "$(build_payload 'cuanto cuestan los floorliner de weathertech?')"
}

test_5() {
  run_test 5 "Fitment con marca/modelo/año común" \
    "$(build_payload 'tengo una toyota hilux 2022 que portabicicletas me sirve')"
}

test_6() {
  run_test 6 "Mensaje vacío (debe filtrarse)" \
    "$(build_payload '')"
}

test_7() {
  run_test 7 "Conversación multi-turno (mismo USER_ID, segundo mensaje)" \
    "$(build_payload 'y para mi otro carro que es un kia sportage 2021?')"
}

# ───────── Runner ─────────

if [ -n "$1" ]; then
  "test_$1"
else
  for i in 1 2 3 4 5 6 7; do
    "test_$i"
    sleep 2  # pausa para no saturar
  done
fi

echo
echo -e "${GREEN}Todas las pruebas enviadas.${NC}"
echo -e "${YELLOW}Para ver el razonamiento del agente (tools llamados, reasoning):${NC}"
echo "   https://n8n.yavingos.com/executions"
