# 08 · Genie: preguntas de negocio en lenguaje natural

## Capa semántica

La última tarea del job (`semantic_layer`) crea estas vistas en español. Tanto la vista como cada columna llevan su definición de negocio. Están definidas en `src/semantic.py` y se testean en `tests/test_semantic.py`.

| Vista | Uso |
|---|---|
| `tiendas` | Tiendas de AndesMart (una fila por tienda). |
| `kpi_semanal` | KPIs semanales por país, tienda, categoría y talla. Usar para tendencias y comparaciones de quiebre de stock y ventas. La semana empieza el lunes. |
| `quiebres_diarios` | Estado de stock al cierre de cada día por tienda y SKU (prenda-color-talla). Usar para preguntas por SKU, por día o sobre días de cobertura. |
| `curva_tallas` | Participación de cada talla en las ventas vs. en el stock, por categoría (todo el período). Si participacion_stock < participacion_ventas, la talla está sub-surtida. |
| `reposicion_sugerida` | Qué enviar a cada tienda la próxima semana según el forecast. Incluye lo que enviaría la práctica actual (reparto parejo entre tallas) para comparar. |

> ¿Por qué vistas y no las tablas Gold directo? Genie acierta más con nombres y definiciones de negocio. La vista además fija reglas que una IA suele equivocar, por ejemplo "para agregar la tasa de quiebre, sumar numerador y denominador; no promediar tasas".

## Crear el Genie space (UI, ~10 min)

1. Databricks → **Genie → New**.
2. **Data:** agrega las 5 vistas de `workspace.andesmart_dev` (o de `andesmart_prod`).
3. **Title:** `AndesMart · Stock y ventas`. **Description:** "Pregunta en español sobre quiebres de stock, ventas, curva de tallas y reposición sugerida."
4. **Instructions → General instructions:** pega el bloque de abajo.
5. **Instructions → SQL queries:** agrega 3 o 4 de los SQL de referencia (por ejemplo el 1, 4, 6 y 9) como ejemplos.
6. **Benchmarks:** agrega las 10 preguntas con su SQL de referencia y pulsa **Run benchmarks**.
7. Anota los resultados en la tabla de evaluación. Meta (US-05): al menos 8 de 10 correctas.

### General instructions (copiar y pegar)

```
Eres un analista de operaciones de AndesMart, una cadena de tiendas de ropa en Perú (PE), Chile (CL), Colombia (CO) y México (MX). Responde siempre en español.

Definiciones:
- "Quiebre de stock": un SKU activo (vendió en los 28 días previos) que cerró el día sin stock.
- Tasa de quiebre = SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos). Nunca promedies la columna tasa_quiebre entre filas.
- "Ventas perdidas" = ventas_perdidas_usd_est (estimación; dilo así al responder).
- Montos en USD salvo que se pida moneda local.
- La semana empieza el lunes. "Última semana" = MAX(semana) en kpi_semanal. "Últimas 4 semanas" = semana >= MAX(semana) - 21 días.
- "Ropa" = todas las categorías excepto calzado.
- SKU = modelo-color-talla (ej. M005-NEG-M).

Qué vista usar:
- Tendencias, comparaciones por país/tienda/categoría/talla → kpi_semanal
- Detalle por SKU o por día, días de cobertura → quiebres_diarios
- ¿Qué tallas están sub/sobre-surtidas? → curva_tallas
- ¿Qué enviar la próxima semana? Comparar con la práctica actual → reposicion_sugerida

Al responder sobre tallas, recuerda el hallazgo principal: la reposición actual reparte en partes iguales entre tallas, por eso M y L se quiebran y XS/XXL se acumulan.
```

## Evaluación

| # | Pregunta | ¿Correcta? | Nota (qué falló / qué instrucción lo arregló) |
|---|---|---|---|
| 1 | ¿Cuál es la tasa de quiebre de stock general? | | |
| 2 | ¿Qué talla de ropa tiene la mayor tasa de quiebre? | | |
| 3 | ¿Qué país pierde más ventas por quiebres de stock? | | |
| 4 | ¿Cuáles son las 5 tiendas con mayor tasa de quiebre en las últimas 4 semanas? | | |
| 5 | ¿Cuánto vendimos en USD en noviembre por país? | | |
| 6 | ¿En qué tallas de jeans falta stock respecto a lo que se vende? | | |
| 7 | ¿Qué tiendas de Chile tienen más quiebres de talla M en jeans la última semana? | | |
| 8 | ¿Cuántos SKUs están en riesgo de quiebre la próxima semana y cuántas unidades hay que enviar? | | |
| 9 | ¿Cuántas unidades de talla M sugiere el modelo frente al reparto parejo? | | |
| 10 | ¿Cómo evolucionó semana a semana la tasa de quiebre en Perú? | | |

**Resultado:** _/10

## SQL de referencia (benchmarks)

**1. ¿Cuál es la tasa de quiebre de stock general?**
```sql
SELECT SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre FROM workspace.andesmart_dev.kpi_semanal
```

**2. ¿Qué talla de ropa tiene la mayor tasa de quiebre?**
```sql
SELECT talla, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre FROM workspace.andesmart_dev.kpi_semanal WHERE categoria <> 'calzado' GROUP BY talla ORDER BY tasa_quiebre DESC LIMIT 1
```

**3. ¿Qué país pierde más ventas por quiebres de stock?**
```sql
SELECT pais, ROUND(SUM(ventas_perdidas_usd_est), 0) AS ventas_perdidas_usd FROM workspace.andesmart_dev.kpi_semanal GROUP BY pais ORDER BY ventas_perdidas_usd DESC LIMIT 1
```

**4. ¿Cuáles son las 5 tiendas con mayor tasa de quiebre en las últimas 4 semanas?**
```sql
SELECT tienda_id, ciudad, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre FROM workspace.andesmart_dev.kpi_semanal WHERE semana >= (SELECT DATE_ADD(MAX(semana), -21) FROM workspace.andesmart_dev.kpi_semanal) GROUP BY tienda_id, ciudad ORDER BY tasa_quiebre DESC LIMIT 5
```

**5. ¿Cuánto vendimos en USD en noviembre por país?**
```sql
SELECT pais, ROUND(SUM(ventas_usd), 2) AS ventas_usd FROM workspace.andesmart_dev.kpi_semanal WHERE MONTH(semana) = 11 GROUP BY pais ORDER BY ventas_usd DESC
```

**6. ¿En qué tallas de jeans falta stock respecto a lo que se vende?**
```sql
SELECT talla, participacion_ventas, participacion_stock, brecha_stock_vs_ventas FROM workspace.andesmart_dev.curva_tallas WHERE categoria = 'jeans' AND brecha_stock_vs_ventas < 0 ORDER BY brecha_stock_vs_ventas
```

**7. ¿Qué tiendas de Chile tienen más quiebres de talla M en jeans la última semana?**
```sql
SELECT tienda_id, ciudad, SUM(dias_sku_en_quiebre) AS dias_sku_en_quiebre FROM workspace.andesmart_dev.kpi_semanal WHERE pais = 'CL' AND categoria = 'jeans' AND talla = 'M' AND semana = (SELECT MAX(semana) FROM workspace.andesmart_dev.kpi_semanal) GROUP BY tienda_id, ciudad ORDER BY dias_sku_en_quiebre DESC
```

**8. ¿Cuántos SKUs están en riesgo de quiebre la próxima semana y cuántas unidades hay que enviar?**
```sql
SELECT SUM(CAST(riesgo_quiebre_7d AS INT)) AS skus_en_riesgo, SUM(unidades_sugeridas) AS unidades_a_enviar FROM workspace.andesmart_dev.reposicion_sugerida
```

**9. ¿Cuántas unidades de talla M sugiere el modelo frente al reparto parejo?**
```sql
SELECT SUM(unidades_sugeridas) AS modelo, SUM(unidades_reparto_parejo) AS reparto_parejo FROM workspace.andesmart_dev.reposicion_sugerida WHERE talla = 'M'
```

**10. ¿Cómo evolucionó semana a semana la tasa de quiebre en Perú?**
```sql
SELECT semana, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre FROM workspace.andesmart_dev.kpi_semanal WHERE pais = 'PE' GROUP BY semana ORDER BY semana
```

## Preguntas extra para la demo

- "¿Por qué se quiebran más las tallas M y L?" (prueba si usa las instrucciones)
- "Dame las 10 combinaciones tienda-SKU con más venta en riesgo la próxima semana"
- "¿Cuántos días de cobertura tiene la talla M de jeans en Lima?"
