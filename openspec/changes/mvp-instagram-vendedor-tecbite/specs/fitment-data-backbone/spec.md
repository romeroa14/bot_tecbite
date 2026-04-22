# fitment-data-backbone Specification

## Purpose

Definir el contrato SQL unico para resolver compatibilidad vehiculo-producto de forma trazable y estable en MVP.

## Requirements

### Requirement: Canonical Fitment Contract

El sistema MUST mantener un modelo canonico en PostgreSQL para `make`, `model`, `year`, `category`, `sku` y regla de compatibilidad. El runtime de recomendacion SHALL leer compatibilidad solo desde este contrato y MUST NOT inferir compatibilidad sin evidencia SQL.

#### Scenario: Recomendacion comercial valida

- GIVEN una conversacion con `make/model/year/category` completos y un SKU activo compatible en SQL
- WHEN el flujo solicita recomendacion comercial
- THEN la respuesta devuelve SKU compatible y trazabilidad al registro canonico

#### Scenario: Compatibilidad no encontrada

- GIVEN una conversacion con slots completos sin coincidencias compatibles en SQL
- WHEN el flujo solicita recomendacion comercial
- THEN el sistema responde "sin compatibilidad confirmada" y no inventa alternativas

### Requirement: MVP Precision Target

El sistema SHOULD alcanzar al menos 90% de recomendaciones con SKU valido compatible sobre conversaciones con slots minimos completos en ventana movil diaria.

#### Scenario: Precision diaria bajo umbral

- GIVEN el reporte diario de recomendaciones compatibles
- WHEN la precision cae por debajo de 90%
- THEN se registra incidente operativo para correccion de datos/ETL en el mismo dia
