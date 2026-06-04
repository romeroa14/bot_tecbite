# Barras Thule — búsqueda por `attributes` (fuente de verdad)

## Regla de negocio

| Tipo de techo (Instagram) | Correlativo | Patrón en `CarroN` (attributes) | Producto |
|---------------------------|-------------|-----------------------------------|----------|
| D — Techo liso | Kit **5** | `Normal Roof` | Kit + barras Edge/Evo |
| B — Riel integrado/alineado | Kit **6** | `Flush Rail(s)` | Kit + barras Edge/Evo |
| C — Punto de fijación | Kit **7** | `Fixed Point(s)` | Kit + barras Edge/Evo |
| A — Riel elevado | — | `Raised` / railing | **Solo pies** (no kit 5/6/7) |
| E — Canal de agua | — | `Gutter` | **Solo pies** (no kit 5/6/7) |

`search_vehicle_fitment` queda como **fallback legacy**, no como fuente principal.

## Formato `attributes` (ejemplo real)

```text
TOYOTA,Yaris (XP150),4p Sedán,2017-2020,Normal Roof,Edge System:720500,721400,...,Evo System:710500,711200,...
```

Campos por coma: **marca, modelo, carrocería, años, tipo techo, Edge SKUs, Evo SKUs**.

## Flujo conversacional

1. **Marca** → persistir `make` en `instagram_conversation_state`
2. **Modelo** → `model`
3. **Año** → `year`
4. **Tipo de techo** (`ROOF_A`…`E`) → `roof_type`
5. Llamar tool `search_attributes_jsonb` con `{ brand, model, year, roof_type }`
6. Recomendar kit + barras Edge/Evo con `image_url` de `tecbite_product_state`

## Tool `search_attributes_jsonb` (actualizada)

**Input obligatorio:**

```json
{
  "brand": "Toyota",
  "model": "Yaris",
  "year": 2025,
  "roof_type": "ROOF_D"
}
```

**Output:**

```json
{
  "found": true,
  "source": "attributes_jsonb",
  "kit_correl": 5,
  "roof_label": "Techo liso",
  "results": [{ "sku": "5394TH", "title": "Kit Clamp 5394...", "edge_skus": [...], "evo_skus": [...] }],
  "bars": [{ "sku": "711200TH", "title": "Thule WingBar Evo 118", "image_url": "..." }]
}
```

## Despliegue en n8n

1. Importar `n8n/tools/tool_search_attributes_jsonb.json` (workflow `C3Mx8TtH3ABEv178`)
2. Ejecutar `scripts/migrations/20260603_instagram_roof_type.sql` en Postgres
3. Actualizar **AI Agent** system message:
   - Barras: **solo** `search_attributes_jsonb` cuando `make + model + year + roof_type` estén completos
   - No usar `search_vehicle_fitment` como primera opción
4. **Parse State Updates** / **Save Lead State**: guardar `roof_type` desde `QR:ROOF_*`

## Prompt snippet (AI Agent)

```
## BARRAS THULE — BÚSQUEDA POR ATTRIBUTES (OBLIGATORIO)
- Fuente de verdad: search_attributes_jsonb (NO search_vehicle_fitment primero).
- Slots obligatorios: marca, modelo, año, tipo de techo (ROOF_A..E).
- Mapeo techo: D=Kit5/Normal Roof, B=Kit6/Flush Rails, C=Kit7/Fixed Points, A/E=solo pies.
- Solo con los 4 slots completos llama search_attributes_jsonb(brand, model, year, roof_type).
- Recomienda SOLO kits y barras del resultado (results + bars). Incluye [IMG:url] cuando exista image_url.
```
