# sales-observability-security-baseline Specification

## Purpose

Definir baseline MVP de seguridad y observabilidad para operar flujo Instagram-first con trazabilidad y control de riesgo.

## Requirements

### Requirement: Environment Secret Handling

El sistema MUST gestionar credenciales de Instagram y base de datos mediante variables de entorno por ambiente. Los artefactos de codigo, logs y snapshots SHALL NOT exponer secretos en texto plano.

#### Scenario: Inicio de workflow con secretos validos

- GIVEN variables de entorno requeridas configuradas
- WHEN inicia ETL o workflow de Instagram
- THEN el proceso autentica sin leer secretos desde archivos versionados

#### Scenario: Secreto faltante

- GIVEN falta una variable de entorno critica
- WHEN inicia el proceso
- THEN el sistema falla de forma explicita y registra error accionable sin filtrar credenciales

### Requirement: MVP Operational Observability

El sistema MUST emitir metricas y logs estructurados para slots completos, precision de compatibilidad, respuestas tecnicas sin fuente, latencia p95 y errores criticos por etapa.

#### Scenario: Reporte diario MVP

- GIVEN ejecuciones del dia de ETL y conversaciones Instagram
- WHEN se consolida el reporte operativo diario
- THEN se publican los KPIs MVP: >=95% slots completos, >=90% compatibilidad valida, <=5% tecnicas sin fuente, p95 tecnico <=2500 ms

### Requirement: Instagram-First Scope Guardrail

El sistema MAY extenderse a otros canales en el futuro, pero el MVP SHALL limitar la operacion productiva y los KPIs obligatorios al canal Instagram.

#### Scenario: Solicitud de canal adicional en MVP

- GIVEN una solicitud de habilitar otro canal durante fase MVP
- WHEN se evalua el alcance vigente
- THEN se marca fuera de alcance y no bloquea la entrega Instagram-first
