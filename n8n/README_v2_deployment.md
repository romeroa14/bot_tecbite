# Tecbite AI Agent v2 — Tool-Based Architecture

Workflow conversacional de Instagram con **AI Agent + Function Calling** (DeepSeek + 5 tools).

## Por qué v2

| Problema en v1 | Solución en v2 |
|---|---|
| Intent Router por keywords (rígido) | LLM razona con tools |
| SQL fijo por intent | LLM encadena tools dinámicamente |
| Solo consulta `vehicles` (data hasta 2006) | Consulta también `attributes` JSONB (data 2024+) |
| Sin búsqueda semántica | `vector_search_docs` con pgvector |
| `ad_ref` solo en system prompt | `decode_ad_ref` lo estructura como hint |
| Sin memoria multi-turno | `Window Memory` con `sessionKey = user_id` |

## Arquitectura

```
Webhook POST → Filter & Normalize → AI Agent → Instagram Send
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
        DeepSeek Chat Model     Window Memory          5 Tools
        (langchain LM)          (por user_id)         (sub-workflows)
                                                            │
        ┌─────────────────┬─────────────────┬─────────────┬─┴───────────────┐
        ▼                 ▼                 ▼             ▼                 ▼
  decode_ad_ref   search_vehicle_   search_attrs_   search_products_  vector_search_
                  fitment            jsonb           by_brand           docs
  (parser)        vehicles +        tps.attributes  tecbite_product_  pgvector +
                  fitment           JSONB           state              Ollama
```

## Orden de importación en n8n

**IMPORTANTE:** importa los sub-workflows ANTES del workflow principal, porque el principal los referencia por `workflowId`.

1. `tools/tool_decode_ad_ref.json`
2. `tools/tool_search_vehicle_fitment.json`
3. `tools/tool_search_attributes_jsonb.json`
4. `tools/tool_search_products_by_brand.json`
5. `tools/tool_vector_search_docs.json`
6. `instagram_agent_workflow_v2.json`

## Credenciales requeridas en n8n

| Credencial | Tipo | Usada en |
|---|---|---|
| `Tecbite Postgres` | Postgres | Todos los tools que hacen SQL |
| `DeepSeek API` | OpenAI API (baseURL=https://api.deepseek.com, key=sk-...) | DeepSeek Chat Model |

Para crear la credencial DeepSeek:
- Tipo: **OpenAI API**
- API Key: `sk-05890be5fc0b4406a4a8c13180208026`
- Base URL: `https://api.deepseek.com`

## Configuración del Webhook

- Path: `instagram-webhook-v2` (diferente al v1 para poder correr ambos en paralelo durante migración)
- Cuando v2 esté validado, cambiar a `instagram-webhook` y desactivar v1.

## Pruebas locales (sin n8n)

Para validar la lógica de cada tool sin importar el workflow:

```bash
# Verifica que el SQL del tool funciona contra la BD real
psql "postgresql://..." -c "$(cat tools/tool_search_attributes_jsonb.json | jq -r '.nodes[] | select(.name == \"Query Attributes\") | .parameters.query')"
```

## Pruebas por caso de uso

### Caso 1: Mitsubishi Montero Sport 2023 (el caso que falla en v1)

Mensaje: `"Hola para mitsubishi montero sport 2023 tienen"`

**Flujo esperado en v2:**
1. AI Agent llama `search_vehicle_fitment(brand=Mitsubishi, model=Montero Sport, year=2023)`
2. Tool devuelve `{found: false, message: "No se encontró fitment..."}`
3. AI Agent llama `search_attributes_jsonb(brand=Mitsubishi, model=Montero Sport)`
4. Tool devuelve productos con Mitsubishi en attributes (Kit Clamp 1182 Montero/Pajero 99-06, etc.)
5. AI Agent responde: "En sistema tengo Kit Clamp 1182 para Montero 99-06. Para tu 2023 te recomiendo confirmar al WhatsApp 6995-1274..."

### Caso 2: CURT + "precio" (ad_ref)

Mensaje: `"precio"` con `referral.ref = "CURT-HITCH-SYSTEM-199"`

**Flujo esperado:**
1. AI Agent ve `ad_ref` → llama `decode_ad_ref({ad_ref: "CURT-HITCH-SYSTEM-199"})`
2. Tool devuelve `{vendor: CURT, category: HITCH-SYSTEM, price: 199}`
3. AI Agent llama `search_products_by_brand({brand: CURT, category: hitch})`
4. AI Agent responde con productos CURT desde $199 + promo

### Caso 3: Pregunta descriptiva

Mensaje: `"el portabicicletas thule sirve para bici eléctrica?"`

**Flujo esperado:**
1. AI Agent llama `vector_search_docs({query: "portabicicletas thule bici eléctrica", vendor: "thule"})`
2. Tool devuelve chunks relevantes con info sobre e-bike compatibility
3. AI Agent sintetiza respuesta basada en docs reales

## Migración desde v1

1. **Importa v2** con path `instagram-webhook-v2` (paralelo a v1).
2. **Prueba** con cuenta de testing apuntando webhook a v2.
3. **Compara respuestas** v1 vs v2 con los mismos prompts.
4. Cuando v2 esté validado:
   - Desactiva v1.
   - Cambia path de v2 a `instagram-webhook`.
   - Actualiza la URL en Meta Business Suite si cambiaste el path.

## Costos

- DeepSeek API: cada turno cuesta ~1-5 tool calls. Con `deepseek-chat` (~$0.27/1M tokens) un caso completo cuesta ≈ $0.001-0.003.
- Ollama embeddings: locales, sin costo.

## Observabilidad

- Cada tool log en n8n muestra input + output del LLM (auditable).
- El AI Agent expone el reasoning intermedio si activas "verbose" en n8n.

## Pendientes / Mejoras futuras

- [ ] Agregar `Postgres Chat Memory` en lugar de `Window Memory` para persistencia entre reinicios.
- [ ] Agregar tool `create_lead` que persista el contacto si el usuario pide cotización formal.
- [ ] Tool `escalate_to_human` que envíe alerta a Slack/WhatsApp del agente humano cuando el LLM detecte frustración.
- [ ] Métricas: contar tool_calls por intent para detectar patrones.
