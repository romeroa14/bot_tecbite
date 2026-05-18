# Guía Final — Tecbite AI Agent v2 (OpenRouter + DeepSeek)

## Arquitectura final

- **LLM**: DeepSeek via OpenRouter (`deepseek/deepseek-chat`)
- **Agente**: Tools Agent (n8n nativo, funciona perfecto con OpenRouter)
- **Tools**: 5 sub-workflows (ya importados previamente)
- **Costo**: ~$0.14/1M tokens (similar a OpenAI)
- **Ventaja**: Funciona desde cualquier país, tools reconocidos por n8n

## Pasos en n8n (en orden, 5 min)

### 1. Borra el workflow v2 anterior (si existe)

- Ve a **Workflows**
- Si ves "Tecbite AI Agent v2 - Tools Agent (OpenAI)" → click en ⋮ → **Delete**
- Los **sub-workflows tools** NO los borres

### 2. Importa el nuevo JSON

Archivo: `/var/www/html/tecbite/n8n/instagram_agent_workflow_v2.json`

Se llamará: **"Tecbite AI Agent v2 - Tools Agent (OpenRouter + DeepSeek)"**

### 3. Asigna los 5 sub-workflows en cada nodo Tool

En cada uno de los 5 nodos `Tool: ...`:

1. Click en el nodo
2. Campo **Workflow** → cambiar de "By ID" a **"From list"**
3. Selecciona del dropdown:

| Nodo | Sub-workflow a seleccionar |
|---|---|
| `Tool: decode_ad_ref` | `Tool - decode_ad_ref` |
| `Tool: search_vehicle_fitment` | `Tool - search_vehicle_fitment` |
| `Tool: search_attributes_jsonb` | `Tool - search_attributes_jsonb` |
| `Tool: search_products_by_brand` | `Tool - search_products_by_brand` |
| `Tool: vector_search_docs` | `Tool - vector_search_docs` |

### 4. Verifica la credencial OpenRouter

En el nodo **OpenRouter Chat Model**:
- Credential debe ser `OpenRouter API` (tipo OpenAI API)
- Si no aparece, créala:
  - Tipo: **OpenAI API**
  - API Key: tu key de OpenRouter (la que configuraste)
  - Base URL: `https://openrouter.ai/api/v1`

### 5. Activa el workflow

Toggle **Active** arriba a la derecha del editor (se pone verde).

## Prueba con curl

```bash
/var/www/html/tecbite/n8n/test_v2_single.sh
```

El script está configurado para:
- Texto: "Hola para mitsubishi montero sport 2023 tienen"
- Sin ad_ref

## Validación esperada

En **Executions** del workflow después del run:

1. **AI Agent** → debería mostrar iteraciones (tool_calls)
2. **Tool: search_attributes_jsonb** → check verde + datos reales en output
3. **OpenRouter Chat Model** → múltiples llamadas (una por iteración)
4. **Instagram Send** → respuesta enviada (puede fallar por user_id falso, eso es OK)

En la respuesta del agente deberías ver productos REALES de tu BD, NO "Thule EasyFold XT" inventado.

## Si algo falla

- **404 en webhook**: workflow no activado → activa el toggle
- **Credencial roja**: crea/verifica la credencial OpenRouter API
- **Tools no ejecutan**: verifica que los 5 sub-workflows estén asignados en modo "From list"
- **OpenRouter error 401**: API key inválida → revísala en https://openrouter.ai/keys

## Costos

- OpenRouter: $0.14/1M tokens
- Un caso completo (3-5 tools) ≈ $0.001-0.003
- Tus $5 de crédito duran ~1,500-3,000 casos

¡Listo para probar!
