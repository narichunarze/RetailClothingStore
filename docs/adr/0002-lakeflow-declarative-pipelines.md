# ADR-0002 · Lakeflow Declarative Pipelines en lugar de notebooks + jobs manuales

- **Estado:** aceptada
- **Fecha:** 2026-11-25

## Contexto
Necesitamos ingesta incremental, reglas de calidad y dependencias entre tablas, con poco tiempo de desarrollo y poca operación.

## Decisión
Implementar Bronze/Silver/Gold con Lakeflow Declarative Pipelines (antes Delta Live Tables), usando Auto Loader para ingesta y `expectations` para calidad.

## Alternativas consideradas
- **Notebooks PySpark + MERGE manual orquestados con Jobs:** máximo control, pero hay que programar checkpoints, dependencias y calidad a mano.
- **dbt:** excelente para SQL, pero agrega otra herramienta y no cubre ingesta streaming.

## Consecuencias
- (+) Menos código, linaje y métricas de calidad automáticas, serverless.
- (−) Lógica de negocio compleja es menos testeable dentro del pipeline → **la lógica se escribe como funciones PySpark puras en `src/` y se testea con `pytest`; el pipeline solo las invoca.**
