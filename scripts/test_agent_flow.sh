#!/bin/bash
# =============================================================================
# Test Suite — Tecbite Agent Flow via Instagram Webhook
# Simulates real Instagram DM conversations to validate chatbot logic
# 
# Usage: ./test_agent_flow.sh [test_number]
#   Without args: runs ALL tests
#   With arg: runs specific test (e.g., ./test_agent_flow.sh 1)
# =============================================================================

WEBHOOK_URL="http://n8n.yavingos.com/webhook/instagram-webhook"
# Test user ID (fake but consistent format)
TEST_USER="9999999999999"
SLEEP_BETWEEN=6  # seconds between messages to let agent process

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

send_message() {
  local user_id="$1"
  local text="$2"
  local quick_reply_payload="$3"
  local test_label="$4"
  
  local message_obj
  if [ -n "$quick_reply_payload" ]; then
    message_obj="{\"text\": \"$text\", \"quick_reply\": {\"payload\": \"$quick_reply_payload\"}}"
  else
    message_obj="{\"text\": \"$text\"}"
  fi

  local payload='{
    "object": "instagram",
    "entry": [{
      "id": "17841421473742193",
      "time": '$(date +%s)',
      "messaging": [{
        "sender": {"id": "'$user_id'"},
        "recipient": {"id": "17841421473742193"},
        "timestamp": '$(date +%s)',
        "message": '$message_obj'
      }]
    }]
  }'

  echo -e "${CYAN}📤 [$test_label] Sending:${NC} $text ${quick_reply_payload:+(QR: $quick_reply_payload)}"
  
  local response
  response=$(curl -s -w "\n%{http_code}" -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)
  
  local http_code=$(echo "$response" | tail -1)
  local body=$(echo "$response" | head -n -1)
  
  if [ "$http_code" = "200" ]; then
    echo -e "  ${GREEN}✅ HTTP $http_code${NC}"
  else
    echo -e "  ${RED}❌ HTTP $http_code — $body${NC}"
  fi
  
  echo "  ⏳ Waiting ${SLEEP_BETWEEN}s for agent to process..."
  sleep $SLEEP_BETWEEN
}

separator() {
  echo ""
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
  echo -e "${YELLOW}  TEST $1: $2${NC}"
  echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
}

# =============================================================================
# TEST 1: Saludo inicial → Menú principal con QR buttons
# EXPECTED: Bienvenida + [MAIN_MENU] → QR buttons (Barras, Canasta, Portabici, WT, WhatsApp)
# =============================================================================
test_1() {
  separator 1 "Saludo inicial → Menú principal"
  echo -e "${CYAN}ESPERADO: Texto de bienvenida + botones Quick Reply del menú principal${NC}"
  echo -e "${CYAN}  Botones: Barras techo | Canasta/Baúl | Portabici | Alfombras WT | WhatsApp${NC}"
  echo ""
  send_message "$TEST_USER" "Hola" "" "T1"
}

# =============================================================================
# TEST 2: Selección QR → Barras Thule → Pide marca/modelo/año
# EXPECTED: "Perfecto 🙌 ¿Qué producto buscas?" o pedir datos del vehículo
# =============================================================================
test_2() {
  separator 2 "QR: Barras techo → Debe pedir marca/modelo/año"
  echo -e "${CYAN}ESPERADO: Pedir marca, modelo y año del vehículo (SIN buscar productos aún)${NC}"
  echo ""
  send_message "$TEST_USER" "Barras techo" "CAT_BARS" "T2"
}

# =============================================================================
# TEST 3: Proporciona marca/modelo/año → Debe pedir tipo de techo
# EXPECTED: [ROOF_MENU] con imagen y botones A-E
# =============================================================================
test_3() {
  separator 3 "Datos vehículo → Debe pedir tipo de techo con QR"
  echo -e "${CYAN}ESPERADO: Pregunta tipo de techo + botones QR (A Riel elev. | B Riel alin. | ...)${NC}"
  echo -e "${CYAN}  NO debe buscar productos todavía${NC}"
  echo ""
  send_message "$TEST_USER" "Toyota 4Runner 2023" "" "T3"
}

# =============================================================================
# TEST 4: Selección tipo de techo → Debe buscar y mostrar productos
# EXPECTED: Buscar con tools y mostrar opciones con QR 1️⃣ 2️⃣ 3️⃣
# =============================================================================
test_4() {
  separator 4 "QR: Tipo de techo A → Debe buscar y mostrar productos"
  echo -e "${CYAN}ESPERADO: Confirmar tipo elegido + buscar productos + mostrar opciones con precios${NC}"
  echo -e "${CYAN}  Si hay resultados: mostrar 2-3 opciones con botones 1️⃣ 2️⃣ 3️⃣${NC}"
  echo -e "${CYAN}  Si NO hay: escalar a WhatsApp (Dave/Eduardo)${NC}"
  echo ""
  send_message "$TEST_USER" "A" "ROOF_A" "T4"
}

# =============================================================================
# TEST 5: Flujo WeatherTech — Inicio
# EXPECTED: Pedir marca/modelo/año primero
# =============================================================================
test_5() {
  separator 5 "WeatherTech → Pedir datos del vehículo"
  echo -e "${CYAN}ESPERADO: Pedir marca/modelo/año del vehículo${NC}"
  local wt_user="9999999999998"
  send_message "$wt_user" "Alfombras" "CAT_WT" "T5"
}

# =============================================================================
# TEST 6: WeatherTech — Datos + Tipo
# EXPECTED: [WT_MENU] con botones "Por fila" | "Universal"
# =============================================================================
test_6() {
  separator 6 "WT datos vehículo → Debe pedir tipo alfombra con QR"
  echo -e "${CYAN}ESPERADO: Preguntar tipo alfombra + botones QR (Por fila | Universal | WhatsApp)${NC}"
  local wt_user="9999999999998"
  send_message "$wt_user" "Hyundai Tucson 2022" "" "T6"
}

# =============================================================================
# TEST 7: "Más información" sin contexto → Debe repetir menú
# EXPECTED: [MAIN_MENU] — NO debe asumir categoría
# =============================================================================
test_7() {
  separator 7 "Mensaje genérico sin contexto → Debe mostrar menú"
  echo -e "${CYAN}ESPERADO: Repetir menú principal (Caso A de memoria)${NC}"
  echo -e "${CYAN}  NO debe inferir categoría${NC}"
  local gen_user="9999999999997"
  send_message "$gen_user" "Necesito más información" "" "T7"
}

# =============================================================================
# TEST 8: Respuesta sin datos suficientes → NO debe buscar productos
# EXPECTED: Pedir datos faltantes, NO llamar tools
# =============================================================================
test_8() {
  separator 8 "Solo marca sin modelo/año → NO debe buscar productos"
  echo -e "${CYAN}ESPERADO: Pedir modelo y año (NO llamar tools de búsqueda)${NC}"
  local data_user="9999999999996"
  send_message "$data_user" "Quiero barras para Toyota" "" "T8"
}

# =============================================================================
# TEST 9: WhatsApp escalation
# EXPECTED: Mostrar links de Dave y Eduardo
# =============================================================================
test_9() {
  separator 9 "QR: WhatsApp → Mostrar links de asesores"
  echo -e "${CYAN}ESPERADO: Links de WhatsApp de Dave (+50769880471) y Eduardo (+50769504792)${NC}"
  local wa_user="9999999999995"
  send_message "$wa_user" "WhatsApp" "WHATSAPP" "T9"
}

# =============================================================================
# TEST 10: "Menú" → Reinicio explícito
# EXPECTED: [MAIN_MENU] sin importar el estado previo
# =============================================================================
test_10() {
  separator 10 "Palabra clave 'menú' → Reinicio al menú principal"
  echo -e "${CYAN}ESPERADO: Cortar tema anterior + menú principal con botones QR${NC}"
  send_message "$TEST_USER" "Menú" "" "T10"
}

# =============================================================================
# MAIN
# =============================================================================
echo ""
echo -e "${YELLOW}🧪 TECBITE AGENT — TEST SUITE${NC}"
echo -e "${YELLOW}Basado en: FLUJO CHATBOT.docx.pdf${NC}"
echo -e "${YELLOW}Webhook: $WEBHOOK_URL${NC}"
echo ""

if [ -n "$1" ]; then
  test_$1
else
  echo -e "${RED}⚠️  IMPORTANTE: Ejecutar tests individuales para evitar conflictos de memoria${NC}"
  echo -e "${RED}   Cada test usa un user_id diferente para simular conversaciones independientes${NC}"
  echo ""
  echo "Tests disponibles:"
  echo "  1  - Saludo inicial → Menú principal"
  echo "  2  - QR Barras → Pedir datos vehículo"  
  echo "  3  - Datos vehículo → Pedir tipo de techo"
  echo "  4  - Tipo techo A → Buscar y mostrar productos"
  echo "  5  - WeatherTech → Pedir datos vehículo"
  echo "  6  - WT datos → Pedir tipo alfombra"
  echo "  7  - Mensaje genérico → Repetir menú"
  echo "  8  - Solo marca → Pedir datos faltantes"
  echo "  9  - WhatsApp → Links de asesores"
  echo " 10  - Palabra 'menú' → Reinicio"
  echo ""
  echo "Uso: $0 <número>"
  echo "Flujo completo Thule: $0 1 && sleep 8 && $0 2 && sleep 8 && $0 3 && sleep 8 && $0 4"
fi

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Revisa las ejecuciones en n8n para verificar:${NC}"
echo -e "${YELLOW}  1. Qué nodos se ejecutaron${NC}"
echo -e "${YELLOW}  2. Si los tools se llamaron correctamente${NC}"
echo -e "${YELLOW}  3. Si la respuesta del agente es coherente${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
