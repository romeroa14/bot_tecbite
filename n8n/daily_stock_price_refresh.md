# Workflow n8n — Refresco Diario de Stock & Precios

Workflow para mantener `tecbite_product_state.price_amount` y `stock_status` frescos a diario, **construido con nodos nativos de n8n** (sin invocar Python). Operaciones: leer URLs activas de Postgres → fetch PDP → parsear precio + disponibilidad → UPDATE en Postgres.

---

## 1. Decisiones de diseño

| Decisión | Valor | Rationale |
|---|---|---|
| **Frecuencia** | 1× por día @ 04:00 UTC (medianoche Panamá UTC-5) | Catalog cambia raro; horario de bajo tráfico |
| **Alcance** | Solo `is_active = TRUE` | No tocar discontinuados |
| **Lote por ejecución** | 200 SKUs/lote, 5 lotes paralelos | Evitar timeouts y rate-limit del catálogo |
| **Throttle** | `Wait` de 800ms entre PDPs (≈75 req/min) | Mismo orden que el scraper Python |
| **Campos a refrescar** | `price_amount`, `stock_status`, `source_updated_at`, `fresh_until`, `ingested_at`, `content_hash` | NO tocamos `attributes`, `title`, `provenance` (eso es trabajo del scraper full) |
| **Escritura** | Postgres node, query parametrizada | Más simple que reusar UPSERT completo |
| **Errores** | Branch dedicado: log + persistir `last_check_failed` | No bloquear el lote por un PDP roto |

---

## 2. Arquitectura del workflow

```
┌─────────────────┐
│ Schedule        │  cron: 0 4 * * *
│ (04:00 UTC)     │
└────────┬────────┘
         ▼
┌─────────────────────────┐
│ Postgres: SELECT URLs   │  → returns {product_sku, pdp_url}[]
│ FROM tecbite_product_   │     WHERE is_active = TRUE
│ state                   │
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Split In Batches (200)  │  loop hasta agotar
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ HTTP Request (PDP)      │  GET pdp_url, User-Agent custom
│ Continue On Fail: TRUE  │
└────────┬────────────────┘
         ▼
┌─────────────────────────┐         ┌─────────────────────┐
│ IF: response status 200 │── NO ──▶│ Set: mark_failed    │
└────────┬────────────────┘         └──────────┬──────────┘
         │ YES                                 ▼
         ▼                          ┌─────────────────────┐
┌─────────────────────────┐         │ Postgres: UPDATE    │
│ HTML Extract            │         │ SET stock_status =  │
│  - price (regex)        │         │  'check_failed'     │
│  - disponibilidad       │         └─────────────────────┘
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Code Node (JS):         │
│  - parsePrice()         │
│  - mapStock()           │
│  - sha256(payload)      │
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Postgres: UPDATE        │  parametrizado por product_sku
│ tecbite_product_state   │
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ Wait 800ms              │  → vuelve al loop
└─────────────────────────┘
         (al terminar)
         ▼
┌─────────────────────────┐
│ Set: build summary      │
│  total, ok, failed,     │
│  price_changed,         │
│  stock_changed          │
└────────┬────────────────┘
         ▼
┌─────────────────────────┐
│ (Opcional) Slack /      │
│ Email: notification     │
└─────────────────────────┘
```

---

## 3. Nodos paso a paso

### 3.1 `Schedule Trigger`
- **Type**: Schedule Trigger
- **Mode**: `Custom (Cron)`
- **Expression**: `0 4 * * *`

### 3.2 `Postgres — Fetch active SKUs`
- **Type**: Postgres
- **Operation**: Execute Query
- **Credentials**: crear `tecbite-n8n-postgres` apuntando a `n8n.yavingos.com:5433/n8ntecbite_db`, user `postgres`
- **Query**:
  ```sql
  SELECT product_sku, pdp_url
  FROM tecbite_product_state
  WHERE is_active = TRUE
    AND pdp_url IS NOT NULL
  ORDER BY ingested_at ASC NULLS FIRST;
  ```

### 3.3 `Split In Batches`
- **Batch Size**: `200`
- **Reset**: false

### 3.4 `HTTP Request — Fetch PDP`
- **URL**: `={{$json.pdp_url}}`
- **Method**: GET
- **Response Format**: String (HTML)
- **Headers**:
  - `User-Agent`: `Mozilla/5.0 (compatible; TecbiteCatalogBot/1.0)`
- **Options**:
  - **Timeout**: 15000
  - **Continue On Fail**: ✅ TRUE

### 3.5 `IF — Status 200`
- **Condition**: `{{$json.statusCode}}` equals `200` (modo number)
- Salida `false` → branch de fallo (3.5b)

### 3.5b `Postgres — Mark check_failed` (branch fallo)
```sql
UPDATE tecbite_product_state
SET stock_status   = 'check_failed',
    ingested_at    = NOW()
WHERE product_sku  = $1;
```
- **Parameters**: `={{$json.product_sku}}`

### 3.6 `Code — Parse PDP`
- **Mode**: Run Once for Each Item
- **Language**: JavaScript
- **Code**:
  ```js
  const html = $json.body || $json.data || $json;
  const sku  = $json.product_sku;

  // Precio: OpenCart usa <span class="price-new">$X.XX</span> (vigente)
  // y <span class="price-old">$Y.YY</span> (tachado, ignorar).
  // La PRIMERA ocurrencia de `price-new` es siempre el precio del producto principal.
  const priceMatch = html.match(/class=["']price-new["'][^>]*>\s*\$?\s*([\d,]+\.\d{2})/i);
  const price_amount = priceMatch
    ? parseFloat(priceMatch[1].replace(/,/g, ''))
    : null;

  // Stock: la PDP tiene "Disponibilidad: <n>"
  let stock_status = 'discontinued';
  const dispMatch = html.match(/Disponibilidad:\s*([0-9]+|\-)/i);
  if (dispMatch) {
    const n = parseInt(dispMatch[1], 10);
    if (Number.isFinite(n)) {
      stock_status = n > 0 ? 'in_stock' : 'out_of_stock';
    }
  }

  // Hash determinista para detectar cambios
  const crypto = require('crypto');
  const content_hash = crypto
    .createHash('sha256')
    .update(`${sku}|${price_amount}|${stock_status}`)
    .digest('hex');

  return {
    product_sku: sku,
    price_amount,
    stock_status,
    content_hash,
  };
  ```

> **Nota**: si los selectores reales del HTML difieren, ajustá los regex mirando una PDP en `view-source:`. Los valores arriba son los que usa `catalog_scraper.py` hoy.

### 3.7 `Postgres — UPDATE state`
```sql
UPDATE tecbite_product_state
SET price_amount      = $2,
    stock_status      = $3,
    content_hash      = $4,
    source_updated_at = NOW(),
    fresh_until       = NOW() + INTERVAL '24 hours',
    ingested_at       = NOW()
WHERE product_sku = $1
  AND is_active = TRUE;
```
- **Parameters** (en orden):
  1. `={{$json.product_sku}}`
  2. `={{$json.price_amount}}`
  3. `={{$json.stock_status}}`
  4. `={{$json.content_hash}}`

### 3.8 `Wait — Throttle`
- **Amount**: `800`
- **Unit**: Milliseconds

### 3.9 `Set — Build summary` (al terminar el loop)
- **Mode**: Manual mapping
- Campos:
  - `total`: `={{$node["Postgres — Fetch active SKUs"].json.length}}`
  - `failed`: contar branch failed
  - `run_at`: `={{$now.toISO()}}`

### 3.10 (Opcional) `Slack` / `Email`
Notificar si `failed > 50` o si el run completo tarda > 1 hora.

---

## 4. Credencial de Postgres en n8n

Crear una vez en **Credentials → New → Postgres**:

| Campo | Valor |
|---|---|
| Host | `n8n.yavingos.com` |
| Database | `n8ntecbite_db` |
| User | `postgres` |
| Password | `Tecbite20$` |
| Port | `5433` |
| SSL | disable (igual que el resto de workflows) |

Nombre sugerido: `tecbite-n8n-postgres`.

---

## 5. Validación post-deploy (queries para correr con MCP)

```sql
-- 1) ¿Se actualizó hoy?
SELECT date_trunc('hour', ingested_at) AS h, COUNT(*)
FROM tecbite_product_state
WHERE ingested_at >= CURRENT_DATE
GROUP BY 1 ORDER BY 1 DESC;

-- 2) ¿Cuántos failed?
SELECT COUNT(*) FROM tecbite_product_state
WHERE stock_status = 'check_failed' AND ingested_at >= CURRENT_DATE;

-- 3) Cambios de stock vs ayer
SELECT stock_status, COUNT(*)
FROM tecbite_product_state
WHERE is_active GROUP BY 1;
```

---

## 6. Lo que este workflow NO hace (alcance acotado)

- **NO descubre productos nuevos** → eso es trabajo del scraper full (`catalog_scraper.py` o `tecbite_catalog_etl.py` corriendo semanal).
- **NO actualiza `attributes`, `title`, `description`** → solo precio y stock.
- **NO marca `is_active = FALSE`** si un PDP devuelve 404; lo deja como `check_failed` para análisis manual. (Decisión conservadora — evita borrar productos por un blip de red.)

---

## 7. Próximos pasos sugeridos

1. **Importar JSON**: en n8n → menú `Workflows` → `Import from File` → `@/var/www/html/tecbite/n8n/daily_stock_price_refresh.json`. Crea todo el grafo de nodos automáticamente.
2. **Crear la credencial** `tecbite-n8n-postgres` (§4) — el JSON la referencia por nombre.
3. **Prueba acotada**: editar el query del nodo `Postgres — Fetch active SKUs` agregando `LIMIT 5` y ejecutar manualmente para validar el parsing.
4. **Validar parsing**: confirmar que `price_amount` y `stock_status` se actualizaron bien con las queries de §5.
5. **Activar Schedule**: quitar el LIMIT y poner el workflow en estado Active.

### Notas sobre el JSON exportable

- El nodo `Code — Parse PDP` usa `$('Split In Batches (200)').item.json` para recuperar el `product_sku` original (el HTTP Request lo pierde al traer solo el HTML).
- El branch `Mark check_failed` también lee el SKU del contexto del split, no del HTTP fallido.
- `executionOrder: v1` está habilitado para que las ramas del IF se ejecuten en orden previsible.
- El loop al final apunta al `Split In Batches` para procesar el siguiente lote.
