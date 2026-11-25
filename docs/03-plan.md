# 03 · Plan de trabajo (≈ 8–10 días)

Cada fase termina con algo **demostrable**. Marcar con `[x]` al completar.

## Fase 0 · Setup (½ día)
- [ ] Crear cuenta en Databricks Free Edition
- [ ] Instalar Databricks CLI y autenticarse (`databricks auth login`)
- [ ] Crear schemas `andesmart_dev` / `andesmart_prod` y volume `raw`
- [ ] Subir repo a GitHub y configurar secrets (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`)
- **Demo:** `databricks bundle validate` pasa

## Fase 1 · Datos fuente (1 día) — US-01
- [ ] `src/data_gen/generate.py`: productos (modelo × talla × color), tiendas, ventas diarias (temporadas, curva de tallas, efecto clima/feriados, quiebres), devoluciones e inventario
- [ ] Inyectar problemas de calidad a propósito (duplicados, precios negativos, nulos)
- [ ] Ingesta de Open-Meteo (clima) y Nager.Date (feriados) al volume
- **Demo:** archivos crudos en `/Volumes/.../raw/`

## Fase 2 · Bronze + Silver (1½ días) — US-01
- [ ] Bronze con Auto Loader (`read_files` / `cloudFiles`)
- [ ] Silver: tipos, dedupe, expectations (`expect_or_drop`, `expect`), cuarentena
- [ ] Funciones de limpieza puras en `src/` con tests `pytest`
- **Demo:** pipeline verde + métricas de calidad visibles

## Fase 3 · Gold + Dashboard (1½ días) — US-02
- [ ] `gold_daily_sales`, `gold_stockout_daily`, `gold_kpi_store_category`
- [ ] AI/BI Dashboard: quiebres por país/tienda/categoría, tendencia, top SKUs perdidos
- **Demo:** dashboard que responde "¿dónde perdemos ventas?"

## Fase 4 · Orquestación + CI/CD (1 día) — US-06
- [ ] Job: generar/ingestar → pipeline → forecast → refresh dashboard
- [ ] GitHub Actions: lint + tests + validate en PR; deploy prod en `main`
- [ ] Grants en Unity Catalog (rol "store_manager" solo lectura en Gold)
- **Demo:** un merge despliega a prod automáticamente

## Fase 5 · Forecast + reposición (1½ días) — US-03, US-04
- [ ] Baseline naive (misma semana anterior) → medir WAPE
- [ ] Modelo (LightGBM o regresión con features de calendario/clima/lags), tracking en MLflow
- [ ] Registrar modelo en Unity Catalog; batch inference a `gold_demand_forecast`
- [ ] `gold_replenishment_suggestions`: días de cobertura y cantidad sugerida
- **Demo:** "estas 20 tallas/colores se quiebran esta semana en estas tiendas, envía X unidades"

## Fase 6 · Capa de IA para el negocio (1 día) — US-05
- [ ] Genie space sobre tablas Gold con instrucciones y ejemplos de SQL
- [ ] Set de 10 preguntas de evaluación (`docs/genie-eval.md`) y resultado
- [ ] (Opcional) Agente con herramientas (Agent Bricks / Mosaic AI Agent Framework) que explique la sugerencia de reposición
- **Demo:** preguntas en español respondidas correctamente

## Fase 7 · Entrega (½–1 día)
- [ ] README final: problema → solución → resultados → trade-offs → próximos pasos
- [ ] Capturas del dashboard y del linaje en `docs/img/`
- [ ] Video de 3 min "presentación al cliente"
- [ ] Repasar `AI_LOG.md` y preparar historias STAR para la entrevista

## Mapeo con el puesto

| Requisito del puesto | Dónde se demuestra |
|---|---|
| Discovery con negocio, user stories | `docs/01-discovery.md` |
| Arquitectura y decisiones autónomas | `docs/02-architecture.md`, `docs/adr/` |
| Python, SQL, PySpark, pipelines ETL/ELT | `src/pipelines/` |
| Delta Lake, Unity Catalog, Workflows | Fases 2–4 |
| MLflow / Mosaic AI | Fases 5–6 |
| CI/CD y tests | `.github/workflows/`, `tests/` |
| AI-first con criterio | `AI_LOG.md` |
| Comunicación de resultados | README + video |
