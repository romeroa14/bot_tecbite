# Proposal: MVP Instagram vendedor Tecbite

## Intent
Resolver recomendaciones inconsistentes en Instagram por deriva de esquema y falta de estado conversacional persistente. PostgreSQL sera backbone unico; RAG solo soporte tecnico.

## Objectives
- Aumentar precision comercial de recomendacion por vehiculo.
- Mantener contexto conversacional por etapas (`make/model/year/category`).
- Entregar una base minima compatible y escalable.

## Scope
### In Scope
- DDL canonico + migraciones para fitment, catalogo/stock y estado conversacional.
- Endurecimiento ETL de Excel/catalogo con validaciones de calidad.
- Flujo n8n Instagram con slot filling persistente y fallback.
- Retrieval runtime con `pgvector` para explicacion tecnica.
- Baseline de seguridad (secretos por entorno) y observabilidad MVP.

### Out of Scope
- Multicanal y features comerciales avanzadas.
- Reescritura completa de pipelines o cambio de stack.

## Capabilities
### New Capabilities
- `fitment-data-backbone`: contrato SQL unico para compatibilidad.
- `instagram-conversation-state`: estado explicito por etapa y eventos.
- `catalog-sync-availability`: snapshot confiable de catalogo/stock.
- `technical-rag-runtime`: soporte tecnico con retrieval vectorial y fuente.
- `sales-observability-security-baseline`: metricas operativas y secretos seguros.

### Modified Capabilities
- None (no existen specs base en `openspec/specs`).

## Approach
Implementacion incremental: (1) esquema canonico, (2) ETL robusto, (3) estado Instagram, (4) pgvector+observabilidad. Se evita romper contratos y se prioriza robustez de datos.

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `scripts/schema.sql` | Modified | DDL canonico e indices de consulta. |
| `scripts/etl.py` | Modified | Normalizacion y checks de calidad fitment. |
| `scripts/tecbite_catalog_etl.py` | Modified | Consistencia de stock/catalogo. |
| `scripts/thule_docs_ingest.py` | Modified | Alineacion con retrieval vectorial. |
| `n8n/thule_rag_workflow.json` | Modified | Stage routing SQL/RAG + fallback. |

## Impact
- Mayor recomendacion valida y menor handoff por ambiguedad.
- Menor deriva de datos y alucinacion en respuestas tabulares.

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Deriva schema-ETL-workflow | Med | Migraciones versionadas + validacion por corrida. |
| Deterioro de fuente de catalogo | Med | Alertas por completitud/SKU anomalo. |
| Sin tests automatizados | High | Smoke tests por flujo critico + checklist diario. |

## Rollout Strategy
Rollout faseado con monitoreo diario: esquema/ETL -> estado Instagram -> pgvector runtime -> hardening final.

## Rollback Plan
Revertir migracion y workflows por fase; restaurar ultimo snapshot valido. Si falla `pgvector`, volver temporalmente al retrieval documental previo sin tocar recomendacion SQL.

## Dependencies
- PostgreSQL con `pgvector`.
- Credenciales Instagram/BD en variables de entorno.

## Success Criteria
- [ ] >=95% conversaciones con slots minimos completos.
- [ ] >=90% recomendaciones con SKU valido compatible.
- [ ] <=5% respuestas tecnicas sin fuente trazable.
- [ ] Disminucion de handoff por falta de contexto vs baseline.
