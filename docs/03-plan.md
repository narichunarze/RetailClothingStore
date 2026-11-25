# 03 · Plan de trabajo (≈ 8–10 días)

Cada fase termina con algo **demostrable**. Marcar con `[x]` al completar.

## Fase 0 · Setup (½ día)
- [x] Crear cuenta en Databricks Free Edition
- [x] Instalar Databricks CLI y autenticarse (token personal en `~/.databrickscfg`)
- [x] Crear schemas `andesmart_dev` / `andesmart_prod` y volume `raw`
- [x] Subir repo a GitHub y configurar secrets (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`)
- **Demo:** `databricks bundle validate` pasa

## Fase 1 · Datos fuente (1 día) — US-01
- [x] `src/data_gen/generate.py`: productos (modelo × talla × color), tiendas, ventas diarias (temporadas, curva de tallas, efecto clima/feriados, quiebres), devoluciones e inventario
- [x] Inyectar problemas de calidad a propósito (duplicados, precios negativos, nulos)
- [x] Script de ingesta de Open-Meteo (clima) y Nager.Date (feriados) (`ingest_external.py`)
- [x] Ejecutar ingesta externa + generación completa y subir al volume (ver `docs/04-source-data.md`)
- **Demo:** archivos crudos en `/Volumes/.../raw/`

## Fase 2 · Bronze + Silver (1½ días) — US-01
- [x] Bronze con Auto Loader (`cloudFiles`, todo string + `_rescued_data`) y maestros/externos en batch
- [x] Silver: tipos, dedupe, expectations (`expect_all_or_drop`, `expect_all`, `expect_or_fail`), cuarentena con motivo
- [x] Funciones de limpieza puras en `src/transforms.py` con tests `pytest`
- [x] Desplegar y correr el pipeline en Databricks; revisar métricas de calidad y linaje
- **Demo:** pipeline verde + métricas de calidad visibles

## Fase 3 · Gold + Dashboard (1½ días) — US-02
- [x] `gold_daily_sales`, `gold_stockout_daily`, `gold_kpi_weekly`, `gold_size_curve`
- [x] Estimación de venta perdida validada contra la verdad del generador (error ~8%)
- [ ] AI/BI Dashboard (guía en `docs/05-dashboard.md`): quiebres por país/tienda/categoría/talla, tendencia, top SKUs perdidos
- **Demo:** dashboard que responde "¿dónde perdemos ventas?"

## Fase 4 · Orquestación + CI/CD (1 día) — US-06
- [x] Job: pipeline → quality gate (→ forecast en Fase 5)
- [x] GitHub Actions: lint + tests + validate en PR; deploy prod en `main` (ver `docs/06-cicd.md`)
- [x] Activar `DEPLOY_ENABLED` y verificar el primer deploy a prod (deploy + job + quality gate en verde)
- [ ] Grants en Unity Catalog (rol "store_manager" solo lectura en Gold)
- **Demo:** un merge despliega a prod automáticamente

## Fase 5 · Forecast + reposición (1½ días) — US-03, US-04
- [x] Baselines ingenuos (semana anterior, promedio de 4 semanas) → WAPE
- [x] Modelo global HistGradientBoosting (Poisson) con lags, calendario comercial y curva de tallas; tracking en MLflow
- [x] Registro en Unity Catalog con alias `champion` solo si supera al baseline
- [x] `gold_demand_forecast` y `gold_replenishment_suggestions`, con comparación contra el reparto parejo actual
- [x] Tarea `forecast` en el job, después del quality gate (ver `docs/07-forecast.md`)
- [ ] Correr en Databricks y revisar el experimento y el modelo en la UI
- [ ] (Mejora) generar dos años de datos para que el modelo aprenda Black Friday y Navidad
- **Demo:** "estas 20 tallas/colores se quiebran esta semana en estas tiendas, envía X unidades"

## Fase 6 · Capa de IA para el negocio (1 día) — US-05
- [x] Capa semántica: 5 vistas en español con comentarios por columna (tarea `semantic_layer` del job)
- [x] Instrucciones de Genie, SQL de ejemplo y 10 benchmarks con SQL de referencia testeado (`docs/08-genie.md`)
- [x] Crear el Genie Agent en la UI y correr los benchmarks: **12/12** en la 4.ª iteración (meta ≥ 8/10)
- [ ] (Opcional) Agente con herramientas (Agent Bricks / Mosaic AI Agent Framework) que explique la sugerencia de reposición
- **Demo:** preguntas en español respondidas correctamente

## Fase 7 · Entrega (½–1 día)
- [x] README final: problema → hallazgo → solución → resultados → trade-offs → próximos pasos
- [ ] Capturas en `docs/img/`: linaje del pipeline, data quality, MLflow, Genie, dashboard
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
