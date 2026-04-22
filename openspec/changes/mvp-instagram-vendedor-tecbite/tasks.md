# Tasks: MVP Instagram vendedor Tecbite

## Phase 1: Foundation SQL (bloqueante)

- [x] 1.1 [BLOQ] Crear `scripts/migrations/20260422_instagram_state.sql` (state/event + indices). **Done**: apply+rollback OK. **Artefactos**: migration + SQL check.
- [x] 1.2 [BLOQ] Alinear `scripts/schema.sql` al contrato canonico (`make/model/year/category/sku`). **Done**: no drift vs migracion. **Artefactos**: DDL + checklist.
- [x] 1.3 [PAR] Crear en `scripts/sql_helpers.py` `upsert_state`, `idempotency_check`, `fitment_lookup`, `latest_catalog`. **Done**: smoke SQL pasa. **Artefactos**: helpers + smoke query.

## Phase 2: ETL fitment y catalogo

- [x] 2.1 [BLOQ] Endurecer `scripts/etl.py` (esquema canonico + rechazo de carga rota). **Done**: dataset valido pasa, roto falla accionable. **Artefactos**: validadores + logs.
- [x] 2.2 [PAR] Agregar KPI precision compatible (>=90%) en `scripts/etl.py`. **Done**: corrida emite KPI e incidente bajo umbral. **Artefactos**: query KPI + log estructurado.
- [x] 2.3 [BLOQ] Reforzar `scripts/tecbite_catalog_etl.py` (snapshot versionado, retencion ultimo valido, freshness<=24h). **Done**: carga invalida conserva snapshot previo. **Artefactos**: metadata snapshot + fallback flow.
- [x] 2.4 [PAR] Validar SKU/completitud y alertar en `scripts/tecbite_catalog_etl.py`. **Done**: SKU malformado dispara alerta. **Artefactos**: reglas + salida alerta.

## Phase 3: Estado conversacional n8n

- [x] 3.1 [BLOQ] En `n8n/thule_rag_workflow.json` persistir estado por `conversation_id` y evento idempotente por `message_id`. **Done**: reintento no duplica/retrocede. **Artefactos**: workflow + payload duplicado.
- [x] 3.2 [BLOQ] Implementar stage routing (`collect_*`, `recommend`, `handoff`) con slot filling incremental. **Done**: 4 mensajes completan slots y llegan a `recommend`. **Artefactos**: ramas + trace.
- [x] 3.3 [PAR] Conectar branch comercial SQL-first (fitment+catalog). **Done**: nunca inventa precio/stock/compatibilidad. **Artefactos**: nodos SQL + caso no-match.
- [x] 3.4 [PAR] Activar handoff por slots incompletos, no-fit SQL y snapshot stale. **Done**: 3 casos fuerzan `stage=handoff`. **Artefactos**: reglas + logs.

## Phase 4: Runtime tecnico pgvector

- [x] 4.1 [BLOQ] Ajustar `scripts/thule_docs_ingest.py` para `source_ref` trazable por chunk. **Done**: embeddings guardan fuente. **Artefactos**: ingest update + query verificacion.
- [x] 4.2 [BLOQ] Implementar retrieval con threshold y fallback “sin evidencia” (`scripts/sql_helpers.py`/n8n). **Done**: bajo score deriva humano sin alucinacion. **Artefactos**: query pgvector + branch fallback.
- [x] 4.3 [PAR] Aplicar guardrail SQL-first en respuestas tecnicas mixtas. **Done**: dato comercial viene de SQL o “no confirmado”. **Artefactos**: plantilla respuesta + caso mixto.
- [x] 4.4 [PAR] Publicar p95 tecnico<=2500 ms y ratio sin fuente<=5%. **Done**: reporte diario incluye ambos. **Artefactos**: query metrica + reporte.

## Phase 5: Seguridad y observabilidad

- [x] 5.1 [BLOQ] Quitar defaults sensibles y validar env vars en `scripts/etl.py`, `scripts/tecbite_catalog_etl.py`, `scripts/thule_docs_ingest.py`. **Done**: fail-fast sanitizado. **Artefactos**: checks env + errores ejemplo.
- [x] 5.2 [PAR] Estandarizar logs (`stage`, `conversation_id`, `snapshot_version`, `error_code`) en ETL+n8n. **Done**: corrida emite campos obligatorios. **Artefactos**: formato log + muestras.
- [x] 5.3 [PAR] Crear reporte diario Instagram-first con KPIs de specs. **Done**: incluye 95/90/5/p95 objetivos. **Artefactos**: query consolidada + job/workflow.

## Secuencia recomendada (lotes sdd-apply)

- Lote A: 1.1 -> 1.2 -> 1.3.
- Lote B: 2.1 + 2.3; luego 2.2 + 2.4.
- Lote C: 3.1 -> 3.2; luego 3.3 + 3.4.
- Lote D: 4.1 -> 4.2; luego 4.3 + 4.4.
- Lote E: 5.1; luego 5.2 + 5.3.
