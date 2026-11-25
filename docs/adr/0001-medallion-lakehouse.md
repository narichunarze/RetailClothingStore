# ADR-0001 · Arquitectura medallion sobre Delta Lake

- **Estado:** aceptada
- **Fecha:** 2026-11-25

## Contexto
Los datos llegan de fuentes heterogéneas (CSV de POS, JSON de ERP, APIs externas) con problemas de calidad conocidos (duplicados, precios negativos). El negocio necesita tablas confiables y el equipo de ML necesita features reproducibles.

## Decisión
Usar capas Bronze / Silver / Gold en Delta Lake dentro de Unity Catalog.

## Alternativas consideradas
- **Transformar directo a tablas finales:** más rápido al inicio, pero sin trazabilidad ni posibilidad de reprocesar.
- **Data warehouse externo:** agrega otra herramienta y costo; el cliente ya está en Databricks.

## Consecuencias
- (+) Reprocesamiento desde Bronze, linaje claro, calidad aislada en Silver.
- (−) Más tablas que mantener; se mitiga con pipelines declarativos.
