# catalog-sync-availability Specification

## Purpose

Mantener un snapshot confiable de catalogo y stock para evitar respuestas comerciales desactualizadas o inconsistentes.

## Requirements

### Requirement: Catalog Snapshot Integrity

El proceso ETL MUST generar snapshot versionado de catalogo/stock en PostgreSQL con validaciones de esquema, SKU y campos obligatorios. El sistema SHALL rechazar cargas con errores criticos y conservar el ultimo snapshot valido.

#### Scenario: Carga valida

- GIVEN un archivo de origen con estructura y SKUs validos
- WHEN corre la sincronizacion programada
- THEN se publica nuevo snapshot con version y fecha de corte

#### Scenario: Carga invalida

- GIVEN un archivo con columnas faltantes o SKUs malformados
- WHEN corre la sincronizacion
- THEN la carga se marca fallida y el runtime mantiene el snapshot previo

### Requirement: Freshness and Availability

El sistema SHOULD exponer catalogo activo con antiguedad maxima de 24 horas para operaciones MVP de recomendacion en Instagram.

#### Scenario: Snapshot vencido

- GIVEN que el snapshot activo supera 24 horas de antiguedad
- WHEN una consulta comercial requiere precio o disponibilidad
- THEN el sistema reporta alerta operativa y evita afirmar stock no confirmado
