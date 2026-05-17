#!/usr/bin/env bash
# Prueba UN solo caso del agente v2.
# Uso: ./test_v2_single.sh
# Edita el TEXT y AD_REF abajo según el caso que quieras probar.

WEBHOOK="https://n8n.yavingos.com/webhook/instagram-webhook-v2"
USER_ID="987654321"
PAGE_ID="123456789"

# ───── EDITA AQUÍ EL CASO A PROBAR ─────
TEXT="Hola para mitsubishi montero sport 2023 tienen"
AD_REF=""              # ej: "CURT-HITCH-SYSTEM-199" o vacío
AD_ID=""               # ej: "CURT-AD-001" o vacío
# ───────────────────────────────────────

REFERRAL=""
if [ -n "$AD_REF" ]; then
  REFERRAL=",\"referral\":{\"ref\":\"$AD_REF\",\"ad_id\":\"$AD_ID\",\"source\":\"ADS\"}"
fi

PAYLOAD=$(cat <<EOF
{
  "object": "page",
  "entry": [{
    "id": "$PAGE_ID",
    "time": $(date +%s),
    "messaging": [{
      "sender": {"id": "$USER_ID"},
      "recipient": {"id": "$PAGE_ID"},
      "timestamp": $(date +%s)$REFERRAL,
      "message": {
        "mid": "mid.test.$(date +%s%N)",
        "text": "$TEXT"
      }
    }]
  }]
}
EOF
)

echo "─── Payload ───"
echo "$PAYLOAD" | jq -C .
echo
echo "─── POST $WEBHOOK ───"
HTTP=$(curl -s -o /tmp/v2_out.txt -w "%{http_code}" -X POST "$WEBHOOK" \
  -H "Content-Type: application/json" -d "$PAYLOAD")
echo "HTTP: $HTTP"
echo
echo "─── Response body ───"
cat /tmp/v2_out.txt | jq -C . 2>/dev/null || cat /tmp/v2_out.txt
echo
echo
echo "→ Revisa la ejecución completa (tools llamados) en:"
echo "  https://n8n.yavingos.com/executions"
