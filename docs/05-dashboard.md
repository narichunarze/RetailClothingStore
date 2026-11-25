# 05 · Dashboard "Quiebres de stock" (AI/BI)

Pregunta de negocio: **¿dónde y en qué tallas perdemos ventas por falta de stock?**

## Crear el dashboard

1. Databricks → **Dashboards → Create dashboard**. Nombre: `AndesMart · Quiebres de stock`.
2. Pestaña **Data → Create from SQL**: crea los datasets de abajo, cada uno con su nombre.
3. Pestaña del canvas: agrega los widgets de la tabla final.
4. Agrega filtros globales para `country`, `category` y el rango de fechas `week_start`.
5. **Publish**.
6. Para versionarlo en el repo (Fase 4):
   ```bash
   databricks bundle generate dashboard --existing-path "/Workspace/Users/<tu-usuario>/AndesMart · Quiebres de stock.lvdash.json" -t dev
   ```
   Esto crea `resources/*.dashboard.yml` y `src/*.lvdash.json`.

> Reemplaza `andesmart_dev` por tu schema si usaste otro.

## Datasets (SQL)

**kpi_weekly**: base de casi todos los widgets
```sql
SELECT * FROM workspace.andesmart_dev.gold_kpi_weekly
```

**kpi_totals**: contadores principales
```sql
SELECT
  SUM(stockout_sku_days) / SUM(active_sku_days) AS stockout_rate,
  SUM(lost_sales_usd_est)                       AS lost_sales_usd,
  SUM(net_sales_usd)                            AS net_sales_usd,
  SUM(lost_sales_usd_est) / (SUM(net_sales_usd) + SUM(lost_sales_usd_est)) AS lost_share
FROM workspace.andesmart_dev.gold_kpi_weekly
```

**size_curve**: el hallazgo principal
```sql
SELECT category, size, sales_share, stock_share, stock_minus_sales_share, stockout_rate
FROM workspace.andesmart_dev.gold_size_curve
```

**top_lost_skus**: qué reponer primero
```sql
SELECT s.store_id, s.city, s.sku, s.category, s.size, s.color,
       ROUND(SUM(s.lost_sales_usd_est), 0) AS lost_sales_usd,
       SUM(CAST(s.is_stockout AS INT))     AS stockout_days
FROM workspace.andesmart_dev.gold_stockout_daily s
WHERE s.date >= DATE_ADD((SELECT MAX(date) FROM workspace.andesmart_dev.gold_stockout_daily), -28)
GROUP BY ALL
ORDER BY lost_sales_usd DESC
LIMIT 50
```

## Widgets

| # | Widget | Dataset | Configuración |
|---|---|---|---|
| 1 | Counter "Tasa de quiebre" | kpi_totals | `stockout_rate`, formato % |
| 2 | Counter "Ventas perdidas (USD)" | kpi_totals | `lost_sales_usd` |
| 3 | Counter "% de demanda perdida" | kpi_totals | `lost_share`, formato % |
| 4 | Línea "Tasa de quiebre semanal" | kpi_weekly | X `week_start`, Y `SUM(stockout_sku_days)/SUM(active_sku_days)`, color `country` |
| 5 | Barras "Tasa de quiebre por talla" | kpi_weekly | X `size`, Y tasa, color `category`. **El insight clave** |
| 6 | Barras agrupadas "Ventas vs. stock por talla" | size_curve | X `size`, Y `sales_share` y `stock_share`, filtro `category` |
| 7 | Heatmap "Quiebre tienda × categoría" | kpi_weekly | X `category`, Y `store_id`, color tasa |
| 8 | Tabla "Top 50 SKUs con venta perdida (últimas 4 semanas)" | top_lost_skus | ordenada por `lost_sales_usd` |

## Historia para presentar (30 s)

> "Perdemos ~X% de la demanda por quiebres, y no es un problema de volumen: es de **curva de tallas**. M y L representan ~55% de la venta pero reciben el mismo stock que las demás tallas, porque la reposición se reparte en partes iguales. Corregir la curva es la palanca de mayor impacto y no requiere comprar más inventario."
