# Handoff SLA — Tecbite Instagram Agent

## Service Level Agreement

| Metric | Target |
|--------|--------|
| **Response time** | ≤ 15 minutes during business hours |
| **Business hours** | Monday–Friday 09:00–18:00 CLT (UTC-4, Chile continental) |
| **Weekend/holiday coverage** | Best-effort, no SLA |
| **Escalation contact** | Human agent team via internal channel (TBD) |
| **Notification mechanism** | Slack webhook or email (to be configured) |

## Escalation Path

1. **Agent detects handoff condition** — sets `event_type=handoff`, logs `error_code` and `handoff_context` in `instagram_conversation_event`
2. **Notification fired** — handoff payload sent to configured notification channel
3. **Human agent acknowledges** — within 15 min during business hours
4. **Agent reviews context** — make, model, year, category, campaign metadata, error reason
5. **Agent takes over** — responds directly via Instagram DM or internal tool

## Handoff Trigger Conditions

| Error Code | Condition | Priority |
|------------|-----------|----------|
| `NO_SQL_FIT` | Fitment lookup returned zero compatible rows | High |
| `STOCK_UNCONFIRMED` | Stock status is `out_of_stock` or `discontinued`, or snapshot older than 24h | High |
| `LOW_TECH_EVIDENCE` | pgvector similarity below 0.76 threshold | Medium |
| `ZERO_CATALOG` | Catalog lookup returned no rows for the SKU | Medium |

## Handoff Context Payload Schema

```json
{
  "handoff_context": {
    "make": "Toyota",
    "model": "Hilux",
    "year": 2023,
    "category": "Barras de techo",
    "campaign_id": "mid.123456...",
    "ad_id": "238425...",
    "product_tag": "Barras AeroBlade Thule",
    "error_code": "NO_SQL_FIT",
    "conversation_id": "aQ_XnJ4...",
    "last_messages": [
      {"role": "user", "content": "Hola, necesito barras para mi Hilux 2023"},
      {"role": "assistant", "content": "¿Qué categoría de producto buscás?"}
    ]
  }
}
```

## Agent Process

1. Review `error_code` and `handoff_context` to understand the situation
2. Check fitment database or Thule official guide for compatibility
3. If stock issue: verify Tecbite ERP for real-time availability
4. Respond to customer via Instagram within SLA window
5. Update conversation stage in system if needed

## Observability

- Handoff events logged in `instagram_conversation_event` with `event_type='handoff'`
- Daily KPI query (`SQL_INSTAGRAM_DAILY_KPI_REPORT`) tracks handoff volume
- SLA breaches should trigger escalation to team lead
