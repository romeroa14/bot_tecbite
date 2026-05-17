#!/usr/bin/env python3
"""
Script de prueba local para el agente conversacional de Instagram.
Simula el flujo del workflow de n8n para verificar el comportamiento.
"""

import json
import sys


def filter_and_normalize(payload):
    """Simula el nodo Filter & Normalize"""
    body = payload.get("body", payload)
    messaging = body.get("entry", [{}])[0].get("messaging", [{}])[0]
    
    if messaging.get("is_echo") is True:
        return []
    
    text = (messaging.get("message", {}).get("text") or "").strip()
    if not text:
        return []
    
    referral = messaging.get("referral", {})
    ad_ref = (referral.get("ref") or "").strip()
    ad_id = (referral.get("ad_id") or "").strip()
    ad_source = (referral.get("source") or "").strip()
    
    return [{
        "user_id": messaging.get("sender", {}).get("id"),
        "message_text": text,
        "ad_ref": ad_ref,
        "ad_id": ad_id,
        "ad_source": ad_source
    }]


def intent_router(data):
    """Simula el nodo Intent Router"""
    text = data.get("message_text", "").lower()
    
    fitment_kw = ['toyota','honda','ford','chevrolet','hyundai','kia','nissan','mazda','ram','mitsubishi','suzuki','subaru','volkswagen','jeep','dodge','gmc','hilux','fortuner','rav4','4runner','prado','runner','tacoma','tundra','corolla','camry','yaris','crv','hrv','civic','accord','ranger','explorer','silverado','tahoe','tucson','santafe','sportage','sorento','frontier','pathfinder','cx5','cx-5','outlander','montero','vitara','forester','outback','tengo un','mi carro','mi vehículo','mi vehiculo','tengo una','pick up','pickup','camioneta','suv']
    stock_kw = ['precio','costo','cuánto','cuanto','disponible','stock','inventario','tienen','hay','comprar','pagar','vale','sale','oferta','promo']
    
    intent = 'FITMENT' if any(kw in text for kw in fitment_kw) else 'STOCK' if any(kw in text for kw in stock_kw) else 'GENERAL'
    
    return {**data, "intent": intent}


def prepare_deepseek_request(data):
    """Simula el nodo Prepare DeepSeek Request"""
    db_context = data.get("db_context", "")
    message_text = data.get("message_text", "")
    user_id = data.get("user_id", "")
    intent = data.get("intent", "GENERAL")
    ad_ref = data.get("ad_ref", "")
    ad_id = data.get("ad_id", "")
    
    vehicle_rule = '- Si el usuario no ha indicado marca, modelo y año de su vehículo, pídeselos antes de recomendar.' if intent == 'FITMENT' else '- NO pidas datos del vehículo para preguntas de precio o stock. Muestra lo disponible directamente.'
    
    ad_context = f"\nCONTEXTO DEL ANUNCIO DE INSTAGRAM:\n- El usuario hizo clic en un anuncio. Referencia: {ad_ref}{f' (Ad ID: {ad_id})' if ad_id else ''}\n- SI el usuario pregunta por precio, stock o disponibilidad SIN especificar producto, asume que se refiere al producto del anuncio.\n- Usa la referencia del anuncio para inferir marca y categoría antes de preguntar." if ad_ref else ""
    
    system_prompt = f"""Eres el asesor virtual de Tecbite Panama, especialista en accesorios Thule y WeatherTech.

REGLAS:
- Sé amable, breve y directo. Máximo 3 párrafos cortos.
{vehicle_rule}
- NUNCA inventes precios ni SKUs. Usa SOLO los datos que te dan en CONTEXTO.
- Si no hay datos en contexto o el stock es 0, sé honesto y ofrece contacto por Instagram.
- Si hay PROMO en el contexto, mencionalo con entusiasmo.
- Responde SIEMPRE en español.
{ad_context}

CONTEXTO DE BASE DE DATOS:
{db_context or 'Sin contexto SQL (consulta general).'}"""
    
    payload = {
        "model": "deepseek-chat",
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ]
    }
    
    return {
        "payload": json.dumps(payload),
        "user_id": user_id,
        "system_prompt": system_prompt
    }


def run_test_case(test_case):
    """Ejecuta un caso de prueba"""
    print(f"\n{'='*70}")
    print(f"TEST: {test_case['name']}")
    print(f"{'='*70}")
    print(f"Descripción: {test_case['description']}")
    print(f"\n--- Payload ---")
    print(json.dumps(test_case['payload'], indent=2))
    
    # Simular flujo
    print(f"\n--- Flujo del Workflow ---")
    
    # Filter & Normalize
    filtered = filter_and_normalize(test_case['payload'])
    if not filtered:
        print("❌ Filter & Normalize: No se procesó (echo o mensaje vacío)")
        return
    
    data = filtered[0]
    print(f"✅ Filter & Normalize:")
    print(f"   user_id: {data['user_id']}")
    print(f"   message_text: {data['message_text']}")
    print(f"   ad_ref: {data['ad_ref']}")
    print(f"   ad_id: {data['ad_id']}")
    print(f"   ad_source: {data['ad_source']}")
    
    # Intent Router
    data_with_intent = intent_router(data)
    print(f"\n✅ Intent Router:")
    print(f"   intent: {data_with_intent['intent']}")
    print(f"   Esperado: {test_case['expected_intent']}")
    
    if data_with_intent['intent'] != test_case['expected_intent']:
        print(f"   ❌ Intent no coincide")
    else:
        print(f"   ✅ Intent coincide")
    
    # Prepare DeepSeek Request
    deepseek_data = prepare_deepseek_request(data_with_intent)
    print(f"\n✅ Prepare DeepSeek Request:")
    print(f"   user_id: {deepseek_data['user_id']}")
    print(f"   ad_ref usado: {data_with_intent['ad_ref']}")
    
    # Mostrar system prompt (truncado)
    print(f"\n--- System Prompt (primeros 500 chars) ---")
    print(deepseek_data['system_prompt'][:500] + "...")
    
    # Verificar comportamiento esperado
    print(f"\n--- Comportamiento Esperado ---")
    print(test_case['expected_behavior'])
    
    # Verificar si el ad_ref está en el system prompt
    if data_with_intent['ad_ref']:
        if data_with_intent['ad_ref'] in deepseek_data['system_prompt']:
            print(f"\n✅ ad_ref '{data_with_intent['ad_ref']}' está en el system prompt")
        else:
            print(f"\n❌ ad_ref '{data_with_intent['ad_ref']}' NO está en el system prompt")
    
    print(f"\n{'='*70}")


if __name__ == "__main__":
    # Cargar casos de prueba
    with open('/var/www/html/tecbite/n8n/instagram_agent_test_payloads.json') as f:
        test_cases = json.load(f)['test_cases']
    
    # Ejecutar solo los casos nuevos
    new_cases = [tc for tc in test_cases if tc['name'] in ['STOCK - CURT campaña real con precio', 'FITMENT - Mitsubishi Montero Sport 2023']]
    
    for test_case in new_cases:
        run_test_case(test_case)
