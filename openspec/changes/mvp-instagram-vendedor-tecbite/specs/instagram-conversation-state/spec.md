# instagram-conversation-state Specification

## Purpose

Persistir estado conversacional por etapas en Instagram para reducir ambiguedad y handoff por falta de contexto.

## Requirements

### Requirement: Stage-Based Slot Persistence

El sistema MUST persistir por conversacion los slots `make`, `model`, `year`, `category` y el `stage` actual. Cada mensaje entrante SHALL actualizar estado de forma idempotente y registrar evento con marca de tiempo.

#### Scenario: Progresion de slots

- GIVEN una conversacion Instagram nueva sin slots
- WHEN el usuario entrega datos de vehiculo en mensajes sucesivos
- THEN el estado persiste cada slot y avanza el `stage` hasta recomendacion

#### Scenario: Mensaje duplicado

- GIVEN un mensaje ya procesado para una conversacion
- WHEN n8n reintenta la misma entrega
- THEN el estado final no se duplica ni retrocede de etapa

### Requirement: Completion Target for MVP

El sistema SHOULD completar slots minimos (`make/model/year/category`) en al menos 95% de conversaciones que llegan a etapa de recomendacion.

#### Scenario: Monitoreo de completitud

- GIVEN el agregado diario de conversaciones en etapa de recomendacion
- WHEN se calcula el porcentaje de slots minimos completos
- THEN el valor reportado permite verificar cumplimiento del umbral de 95%
