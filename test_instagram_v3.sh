#!/bin/bash
# Test Instagram AI Agent v3 — Images + Quick Replies
# Reemplazá N8N_URL con tu instancia

N8N_URL="${N8N_URL:-https://n8n.yavingos.com}"
WEBHOOK_GET_PATH="instagram-webhook-v2"
WEBHOOK_POST_PATH="instagram-webhook"
USER_ID="${USER_ID:-123456789}"  # Fake user ID for testing

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Tecbite AI Agent v3 — Test Suite                       ║"
echo "║  GET URL:  $N8N_URL/webhook/$WEBHOOK_GET_PATH            ║"
echo "║  POST URL: $N8N_URL/webhook/$WEBHOOK_POST_PATH           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── 1. VERIFY GET (webhook setup) ──
echo "═══ TEST 1: Webhook Verification GET ═══"
curl -s "$N8N_URL/webhook/$WEBHOOK_GET_PATH?hub.mode=subscribe&hub.verify_token=$VERIFY_TOKEN&hub.challenge=TEST123"
echo -e "\n"

# ── 2. SIMPLE TEXT MESSAGE ──
echo "═══ TEST 2: Simple text message ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": { "text": "Hola, qué productos tienen?" }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

# ── 3. VEHICLE QUERY WITH AD_REF ──
echo "═══ TEST 3: Vehicle query from ad ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": { "text": "Qué portaequipajes tenés para mi?" },
        "referral": {
          "ref": "THULE-KIT-MONTERO_SPORT-2023-120",
          "ad_id": "238499123456789",
          "source": "IG_API"
        }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

# ── 4. VEHICLE MENTION (triggers search_vehicle_fitment) ──
echo "═══ TEST 4: Vehicle mention — Montero Sport 2023 ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": { "text": "Tienen accesorios para Mitsubishi Montero Sport 2023?" }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

# ── 5. BRAND QUERY (triggers search_products_by_brand) ──
echo "═══ TEST 5: Brand query — Thule ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": { "text": "Qué portabicicletas Thule tienen?" }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

# ── 6. QUICK REPLY SIMULATION ──
echo "═══ TEST 6: Quick Reply — user taps 1️⃣ (SELECT_0) ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": {
          "quick_reply": {
            "payload": "SELECT_0"
          }
        }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

# ── 7. QUICK REPLY — WhatsApp ──
echo "═══ TEST 7: Quick Reply — user taps 📞 WhatsApp ═══"
curl -s -X POST "$N8N_URL/webhook/$WEBHOOK_POST_PATH" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "instagram",
    "entry": [{
      "messaging": [{
        "sender": { "id": "'$USER_ID'" },
        "recipient": { "id": "17841400000000000" },
        "message": {
          "quick_reply": {
            "payload": "WHATSAPP"
          }
        }
      }]
    }]
  }' | python3 -m json.tool 2>/dev/null || true
echo -e "\n"

echo "═══════════════════════════════════════════════════════════"
echo "Tests completados."
echo "Revisá en n8n Execution History los resultados de cada test."
echo ""
echo "Variables de entorno:"
echo "  N8N_URL=$N8N_URL"
echo "  USER_ID=$USER_ID"
echo ""
echo "Ejemplo con URL personalizada:"
echo "  N8N_URL=https://mi-n8n.com USER_ID=999999 ./test_instagram_v3.sh"
echo "═══════════════════════════════════════════════════════════"
