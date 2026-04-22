# technical-rag-runtime Specification

## Purpose

Entregar soporte tecnico con retrieval vectorial en PostgreSQL `pgvector`, manteniendo separacion estricta entre asesoria tecnica y decision comercial.

## Requirements

### Requirement: Technical Retrieval with Sources

El runtime tecnico MUST recuperar contexto desde `pgvector` y SHALL incluir al menos una fuente trazable por respuesta tecnica. El sistema SHOULD mantener <=5% de respuestas tecnicas sin fuente trazable en medicion diaria.

#### Scenario: Respuesta tecnica con evidencia

- GIVEN una consulta tecnica de instalacion o uso
- WHEN el runtime ejecuta retrieval sobre documentos indexados
- THEN la respuesta incluye recomendacion tecnica y referencia de fuente

#### Scenario: Sin evidencia suficiente

- GIVEN una consulta tecnica sin chunks relevantes
- WHEN el score de retrieval no supera umbral minimo
- THEN el sistema responde falta de evidencia y solicita derivacion humana

### Requirement: SQL-First Guardrail for Commercial Facts

El sistema MUST NOT alucinar precio, stock o compatibilidad en respuestas tecnicas. Si la consulta incluye hechos comerciales, el runtime SHALL resolverlos via SQL canonico o declarar dato no confirmado.

#### Scenario: Consulta mixta tecnica-comercial

- GIVEN una pregunta que combina instalacion con precio y compatibilidad
- WHEN el flujo genera respuesta
- THEN los hechos comerciales salen de SQL o se marcan no confirmados, nunca inferidos por RAG

### Requirement: MVP Latency Target

El runtime SHOULD mantener latencia p95 <= 2500 ms para respuestas tecnicas en condiciones operativas normales de MVP.

#### Scenario: Validacion de latencia p95

- GIVEN metricas de latencia del runtime tecnico en ventana diaria
- WHEN se calcula p95 de respuestas exitosas
- THEN el valor permite verificar cumplimiento del objetivo <= 2500 ms
