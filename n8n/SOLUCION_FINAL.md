# Solución Final — Tecbite AI Agent v2 (ReAct + DeepSeek)

## Qué cambió respecto al intento anterior

| Antes (Tools Agent) | Ahora (ReAct Agent) |
|---|---|
| `agent` no especificado (usaba Tools Agent default) | `agent: "reActAgent"` |
| Tools no se pasaban a DeepSeek (limitación n8n + custom baseURL) | Tools se describen al LLM en texto, ReAct via prompt |
| `tool_calls: []` siempre | LLM emite `Action: tool_name\nAction Input: {...}` que n8n parsea y ejecuta |
| Schema de input ausente | Cada tool tiene `inputSchema` JSON Schema explícito |
| temp 0.3, baseURL sin /v1 | temp 0, baseURL `https://api.deepseek.com/v1` |

## Por qué ReAct sí funciona con DeepSeek

ReAct **no requiere function calling nativo del LLM**. Funciona puramente por instrucciones de texto:

```
Available tools:
- search_vehicle_fitment: Busca productos compatibles...
- search_attributes_jsonb: ...

Use this format:
Thought: razonamiento
Action: nombre_tool
Action Input: {"brand": "...", "model": "..."}
Observation: resultado de la tool
... (puedes repetir Thought/Action/Observation hasta 5 veces)
Final Answer: respuesta al cliente
```

DeepSeek-V3 es excelente siguiendo este patrón. Era el método estándar antes de OpenAI Functions.

## Pasos para aplicar (en orden)

### 1. Borra el workflow v2 anterior en n8n

Tienes uno fallido importado. Bórralo desde la UI: **Workflows → Tecbite AI Agent v2 - Tool-Based → ⋮ → Delete**.

Los **5 sub-workflows tools** (Tool - decode_ad_ref, etc.) **NO los borres**, los reutilizamos.

### 2. Importa el nuevo JSON

`/var/www/html/tecbite/n8n/instagram_agent_workflow_v2.json`

Se llamará **"Tecbite AI Agent v2 - ReAct (DeepSeek)"**.

### 3. Asigna manualmente el workflow a cada Tool

Esto sigue siendo necesario (n8n no preserva IDs). En cada uno de los 5 nodos `Tool: ...`:

- Click en el nodo
- Campo **Workflow** → modo **From list**
- Selecciona el sub-workflow correspondiente:

| Nodo | Sub-workflow a seleccionar |
|---|---|
| `Tool: decode_ad_ref` | `Tool - decode_ad_ref` |
| `Tool: search_vehicle_fitment` | `Tool - search_vehicle_fitment` |
| `Tool: search_attributes_jsonb` | `Tool - search_attributes_jsonb` |
| `Tool: search_products_by_brand` | `Tool - search_products_by_brand` |
| `Tool: vector_search_docs` | `Tool - vector_search_docs` |

### 4. Verifica la credencial DeepSeek

En el nodo **DeepSeek Chat Model**:
- Credential debe ser `DeepSeek API` (tipo OpenAI API)
- Si no existe, créala: API Key = `sk-05890be5fc0b4406a4a8c13180208026`, Base URL = `https://api.deepseek.com/v1`

### 5. Activa el workflow

Toggle **Active** arriba a la derecha.

### 6. Prueba con curl

```bash
/var/www/html/tecbite/n8n/test_v2_single.sh
```

Edita el archivo para cambiar el caso. Probemos primero con Mitsubishi Montero Sport 2023.

## Validación esperada

En **Executions** del workflow v2 después de un run exitoso, deberías ver:

1. **AI Agent** con múltiples iteraciones (Thought → Action → Observation)
2. **Tool: search_attributes_jsonb** con check verde y datos reales en el output
3. **DeepSeek Chat Model** con varias llamadas (una por iteración del ReAct)
4. La respuesta final del agente menciona productos REALES de tu BD (no "Thule EasyFold XT" inventado)

## Si aún no llama tools después de esto

Casos extremos posibles:
- DeepSeek está respondiendo `Final Answer:` sin pasar por `Action:` → endurece más el system prompt
- n8n no parsea el formato ReAct de DeepSeek → revisar logs del nodo AI Agent

En ese caso, refactorizamos a un **agent loop manual** con HTTP Request nodes (control total).
