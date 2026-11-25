# 07 · Forecast de demanda y reposición

## Decisiones clave

| Decisión | Por qué |
|---|---|
| **Grano semanal, la semana empieza el lunes** | Así decide el planner: pide el lunes y la mercadería llega el jueves. Además reduce 2,4M filas diarias a ~350k |
| **Target = venta + venta perdida estimada** | La venta está *censurada* en los días de quiebre. Entrenar solo con venta subestimaría justo las tallas M y L. La venta perdida viene de Gold, validada contra la verdad (~8% de error) |
| **Un solo modelo global** (HistGradientBoosting, pérdida Poisson) | Un modelo por SKU no tendría historia suficiente. Poisson se ajusta a conteos con ceros. Está en scikit-learn, así que no hace falta instalar nada en serverless |
| **Features solo con lo que se sabe el lunes** | Lags y promedios de semanas anteriores, más el calendario comercial planificado (eventos, feriados, temporada, liquidaciones). No se usa el clima real de la semana objetivo, porque eso sería usar el futuro (leakage) |
| **Siempre contra un baseline** | El modelo solo recibe el alias `champion` en Unity Catalog si supera al mejor baseline ingenuo |

## Resultados del backtest (últimas 8 semanas, datos por defecto)

| Nivel | Modelo | Promedio 4 semanas | Semana anterior |
|---|---|---|---|
| Tienda × SKU | **0,50** | 0,52 | 0,62 |
| Tienda × modelo-color | **0,32** | 0,33 | 0,40 |
| País × categoría | **0,25** | 0,26 | 0,32 |

Cómo interpretarlo:
- A nivel SKU hay unas 2,6 unidades por semana. Con demanda Poisson, el error mínimo posible ronda 0,45–0,5, así que el modelo está cerca de ese piso. **El valor no está en el WAPE por SKU sino en la distribución entre tallas** (ver abajo).
- Las 8 semanas de prueba incluyen Black Friday y Navidad, que el modelo nunca vio porque hay un solo año de historia. **Siguiente paso:** generar dos años (`--start 2024-01-01 --days 730`).

## Reposición (`src/ml/replenishment.py`)

Política de revisión periódica:
- **Cobertura:** lead time (3 días) más el período hasta la próxima revisión (7 días).
- **Stock de seguridad:** 1,65·√cobertura, para un nivel de servicio de ~95% con demanda Poisson.
- **Sugerido:** `max(stock objetivo − (on_hand + in_transit), 0)`.

La tabla `gold_replenishment_suggestions` incluye `even_split_units`, lo que habría enviado la práctica actual: el mismo total repartido igual entre tallas. Ejemplo con los datos por defecto (sin calzado):

| Talla | Modelo | Reparto parejo |
|---|---|---|
| XS | 0 | 489 |
| S | 359 | 489 |
| M | **2.832** | 489 |
| L | **1.697** | 489 |
| XL | 109 | 489 |
| XXL | 0 | 489 |

> **Mensaje para el negocio:** "No hace falta comprar más; hace falta enviar la curva de tallas correcta a cada tienda."

## Artefactos

| Qué | Dónde |
|---|---|
| Experimento | MLflow → `/Users/<tú>/andesmart-demand-forecast` (métricas por talla, parámetros) |
| Modelo | Unity Catalog → `workspace.<schema>.demand_forecast`, alias `champion` |
| Predicciones | `gold_demand_forecast` |
| Reposición | `gold_replenishment_suggestions` (ordenada por `at_risk_sales_usd`) |
| Código | `src/ml/` (tests en `tests/test_ml.py`), notebook del job `src/jobs/forecast.py` |
