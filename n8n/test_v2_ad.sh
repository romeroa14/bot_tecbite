#!/bin/bash

# Script de prueba para Instagram Agent v2 - Simula mensaje desde anuncio
# Prueba la tool decode_ad_ref + búsqueda de productos

# Configuración
WEBHOOK="https://n8n.yavingos.com/webhook/instagram-webhook-v2"
USER_ID="987654321"
PAGE_ID="123456789"

# Datos del anuncio simulado
# Formato: VENDOR-CATEGORY-MODEL-YEAR-PRICE
AD_REF="THULE-Portabicicletas-Montero Sport-2023-450"
AD_ID="ad_123456789"
AD_TITLE="Portabicicletas Thule para Mitsubishi Montero Sport 2023 - Transporta hasta 4 bicicletas"

# Mensaje del usuario
TEXT="Hola, me interesa el anuncio que vi"

# Payload del webhook de Instagram con contexto de anuncio
PAYLOAD=$(cat <<EOF
{
  "object": "page",
  "entry": [
    {
      "id": "${PAGE_ID}",
      "time": $(date +%s),
      "messaging": [
        {
          "sender": {
            "id": "${USER_ID}"
          },
          "recipient": {
            "id": "${PAGE_ID}"
          },
          "timestamp": $(date +%s),
          "message": {
            "mid": "mid.test.$(date +%s)",
            "text": "${TEXT}"
          },
          "referral": {
            "ref": "${AD_REF}",
            "source": "ADS",
            "type": "OPEN_THREAD",
            "ad_id": "${AD_ID}",
            "ad_title": "${AD_TITLE}"
          }
        }
      ]
    }
  ]
}
EOF
)

echo "─── Payload ───"
echo "$PAYLOAD" | jq .
echo ""

echo "─── POST ${WEBHOOK} ───"
RESPONSE=$(curl -s -X POST "$WEBHOOK" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$WEBHOOK" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

echo "HTTP: $HTTP_CODE"
echo ""

echo "─── Response body ───"
echo "$RESPONSE" | jq .
echo ""

if [ "$HTTP_CODE" = "200" ]; then
  echo "→ Revisa la ejecución completa en:"
  echo "  https://n8n.yavingos.com/executions"
else
  echo "❌ Error: HTTP $HTTP_CODE"
fi
