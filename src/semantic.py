"""Capa semántica para Genie: vistas en español, con definiciones de negocio por columna.

Genie (y cualquier usuario de negocio) entiende mejor `tasa_quiebre` con su definición
que `stockout_sku_days / active_sku_days`. Las vistas se recrean en cada corrida del job.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class View:
    name: str
    comment: str
    columns: list[tuple[str, str, str]]  # (alias, expresión SQL, comentario)
    from_sql: str                         # FROM ... (con {t} para nombres de tabla)


VIEWS = [
    View(
        "tiendas",
        "Tiendas de AndesMart (una fila por tienda).",
        [
            ("tienda_id", "store_id", "Código de la tienda, ej. S001"),
            ("tienda", "store_name", "Nombre de la tienda"),
            ("pais", "country", "País (código ISO): PE Perú, CL Chile, CO Colombia, MX México"),
            ("ciudad", "city", "Ciudad de la tienda"),
            ("formato", "store_format", "Formato: mall, calle u outlet"),
            ("moneda", "currency", "Moneda local de la tienda"),
        ],
        "FROM {t[silver_stores]}",
    ),
    View(
        "kpi_semanal",
        "KPIs semanales por país, tienda, categoría y talla. Usar para tendencias y "
        "comparaciones de quiebre de stock y ventas. La semana empieza el lunes.",
        [
            ("semana", "k.week_start", "Lunes de inicio de la semana"),
            ("pais", "k.country", "País (PE, CL, CO, MX)"),
            ("tienda_id", "k.store_id", "Código de la tienda"),
            ("ciudad", "s.city", "Ciudad de la tienda"),
            ("categoria", "k.category",
             "Categoría: polos, shorts, vestidos, casacas, chompas, jeans, camisas, calzado"),
            ("talla", "k.size", "Talla: XS, S, M, L, XL, XXL (ropa) o 36–43 (calzado)"),
            ("unidades_vendidas", "k.units_sold", "Unidades vendidas en la semana"),
            ("ventas_usd", "k.net_sales_usd", "Venta neta de devoluciones, en USD"),
            ("dias_sku_activos", "k.active_sku_days",
             "Días-SKU con venta en los 28 días previos (denominador de la tasa de quiebre)"),
            ("dias_sku_en_quiebre", "k.stockout_sku_days",
             "Días-SKU activos que cerraron el día sin stock"),
            ("tasa_quiebre", "k.stockout_rate",
             "dias_sku_en_quiebre / dias_sku_activos. Para agregar, sumar numerador y "
             "denominador; NO promediar tasas"),
            ("unidades_perdidas_est", "k.lost_units_est",
             "Unidades que se habrían vendido si hubiera habido stock (estimado)"),
            ("ventas_perdidas_usd_est", "k.lost_sales_usd_est",
             "Venta perdida estimada por quiebres, en USD a precio de lista"),
        ],
        "FROM {t[gold_kpi_weekly]} k LEFT JOIN {t[silver_stores]} s ON k.store_id = s.store_id",
    ),
    View(
        "quiebres_diarios",
        "Estado de stock al cierre de cada día por tienda y SKU (prenda-color-talla). "
        "Usar para preguntas por SKU, por día o sobre días de cobertura.",
        [
            ("fecha", "date", "Fecha del cierre"),
            ("tienda_id", "store_id", "Código de la tienda"),
            ("pais", "country", "País"),
            ("ciudad", "city", "Ciudad"),
            ("sku", "sku", "SKU = modelo-color-talla, ej. M005-NEG-M"),
            ("modelo_id", "model_id", "Modelo de prenda (agrupa colores y tallas)"),
            ("categoria", "category", "Categoría de producto"),
            ("talla", "size", "Talla"),
            ("color", "color", "Color"),
            ("stock_cierre", "on_hand", "Unidades en tienda al cierre (completado si faltó el dato)"),
            ("en_transito", "in_transit", "Unidades en camino desde el almacén"),
            ("unidades_vendidas", "units_sold", "Unidades vendidas ese día"),
            ("sku_activo", "is_active", "true si el SKU vendió en los 28 días previos"),
            ("en_quiebre", "is_stockout", "true si el SKU está activo y cerró sin stock"),
            ("dias_cobertura", "days_of_cover", "Días que alcanza el stock al ritmo de venta reciente"),
            ("unidades_perdidas_est", "lost_units_est", "Venta perdida estimada del día (unidades)"),
            ("ventas_perdidas_usd_est", "lost_sales_usd_est", "Venta perdida estimada del día (USD)"),
        ],
        "FROM {t[gold_stockout_daily]}",
    ),
    View(
        "curva_tallas",
        "Participación de cada talla en las ventas vs. en el stock, por categoría (todo el "
        "período). Si participacion_stock < participacion_ventas, la talla está sub-surtida.",
        [
            ("categoria", "category", "Categoría"),
            ("talla", "size", "Talla"),
            ("unidades_vendidas", "units_sold", "Unidades vendidas en el período"),
            ("participacion_ventas", "sales_share", "Fracción de las ventas de la categoría (0–1)"),
            ("participacion_stock", "stock_share", "Fracción del stock promedio de la categoría (0–1)"),
            ("brecha_stock_vs_ventas", "stock_minus_sales_share",
             "participacion_stock - participacion_ventas. Negativo = falta stock en esa talla"),
            ("tasa_quiebre", "stockout_rate", "Fracción de días-SKU en quiebre"),
        ],
        "FROM {t[gold_size_curve]}",
    ),
    View(
        "reposicion_sugerida",
        "Qué enviar a cada tienda la próxima semana según el forecast. Incluye lo que "
        "enviaría la práctica actual (reparto parejo entre tallas) para comparar.",
        [
            ("semana_objetivo", "forecast_week_start", "Lunes de la semana pronosticada"),
            ("tienda_id", "store_id", "Código de la tienda"),
            ("pais", "country", "País"),
            ("sku", "sku", "SKU"),
            ("modelo_id", "model_id", "Modelo"),
            ("categoria", "category", "Categoría"),
            ("talla", "size", "Talla"),
            ("color", "color", "Color"),
            ("demanda_pronosticada_7d", "demand_7d_pred", "Unidades que se espera vender en la semana"),
            ("stock_actual", "on_hand", "Stock en tienda hoy"),
            ("en_transito", "in_transit", "Unidades en camino"),
            ("unidades_sugeridas", "suggested_units", "Unidades a enviar (cubre 10 días + seguridad)"),
            ("unidades_reparto_parejo", "even_split_units",
             "Lo que enviaría la práctica actual: mismo total repartido igual entre tallas"),
            ("diferencia_vs_reparto_parejo", "delta_vs_even_split",
             "unidades_sugeridas - unidades_reparto_parejo"),
            ("riesgo_quiebre_7d", "stockout_risk_7d", "true si el stock no cubre la demanda de la semana"),
            ("dias_cobertura", "days_of_cover", "Días que alcanza el stock actual"),
            ("ventas_en_riesgo_usd", "at_risk_sales_usd", "Venta que se perdería sin reponer (USD)"),
            ("version_modelo", "model_version", "Versión del modelo de forecast usada"),
        ],
        "FROM {t[gold_replenishment_suggestions]}",
    ),
]


def _q(s: str) -> str:
    return s.replace("'", "''")


def create_view_sql(view: View, table: dict[str, str], target: str, temp: bool = False) -> str:
    """CREATE OR REPLACE VIEW con comentarios por columna.

    `table` mapea nombre lógico -> nombre completo; `target` es el nombre de la vista.
    """
    cols = ",\n  ".join(f"{a} COMMENT '{_q(c)}'" for a, _, c in view.columns)
    select = ",\n  ".join(f"{e} AS {a}" for a, e, _ in view.columns)
    kind = "TEMP VIEW" if temp else "VIEW"
    comment = "" if temp else f"\nCOMMENT '{_q(view.comment)}'"
    return (f"CREATE OR REPLACE {kind} {target} (\n  {cols}\n){comment}\nAS SELECT\n  {select}\n"
            + view.from_sql.format(t=table))


# --------------------------------------------------------------------------- benchmarks de Genie
# Preguntas de evaluación con su SQL de referencia ("ground truth"). Se cargan en
# Genie → Benchmarks y también se ejecutan en tests/test_semantic.py.
# `{s}` = prefijo catálogo.schema (ej. "workspace.andesmart_dev.").

LAST_4_WEEKS = "semana >= (SELECT DATE_ADD(MAX(semana), -21) FROM {s}kpi_semanal)"

BENCHMARKS: list[tuple[str, str]] = [
    ("¿Cuál es la tasa de quiebre de stock general?",
     "SELECT SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre "
     "FROM {s}kpi_semanal"),
    ("¿Qué talla de ropa tiene la mayor tasa de quiebre?",
     "SELECT talla, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre "
     "FROM {s}kpi_semanal WHERE categoria <> 'calzado' "
     "GROUP BY talla ORDER BY tasa_quiebre DESC LIMIT 1"),
    ("¿Qué país pierde más ventas por quiebres de stock?",
     "SELECT pais, ROUND(SUM(ventas_perdidas_usd_est), 0) AS ventas_perdidas_usd "
     "FROM {s}kpi_semanal GROUP BY pais ORDER BY ventas_perdidas_usd DESC LIMIT 1"),
    ("¿Cuáles son las 5 tiendas con mayor tasa de quiebre en las últimas 4 semanas?",
     "SELECT tienda_id, ciudad, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre "
     "FROM {s}kpi_semanal WHERE " + LAST_4_WEEKS + " "
     "GROUP BY tienda_id, ciudad ORDER BY tasa_quiebre DESC LIMIT 5"),
    ("¿Cuánto vendimos en USD en noviembre por país?",
     "SELECT pais, ROUND(SUM(ventas_usd), 2) AS ventas_usd FROM {s}kpi_semanal "
     "WHERE MONTH(semana) = 11 GROUP BY pais ORDER BY ventas_usd DESC"),
    ("¿En qué tallas de jeans falta stock respecto a lo que se vende?",
     "SELECT talla, participacion_ventas, participacion_stock, brecha_stock_vs_ventas "
     "FROM {s}curva_tallas WHERE categoria = 'jeans' AND brecha_stock_vs_ventas < 0 "
     "ORDER BY brecha_stock_vs_ventas"),
    ("¿Qué tiendas de Chile tienen más quiebres de talla M en jeans la última semana?",
     "SELECT tienda_id, ciudad, SUM(dias_sku_en_quiebre) AS dias_sku_en_quiebre "
     "FROM {s}kpi_semanal WHERE pais = 'CL' AND categoria = 'jeans' AND talla = 'M' "
     "AND semana = (SELECT MAX(semana) FROM {s}kpi_semanal) "
     "GROUP BY tienda_id, ciudad ORDER BY dias_sku_en_quiebre DESC"),
    ("¿Cuántos SKUs están en riesgo de quiebre la próxima semana y cuántas unidades hay que enviar?",
     "SELECT SUM(CAST(riesgo_quiebre_7d AS INT)) AS skus_en_riesgo, "
     "SUM(unidades_sugeridas) AS unidades_a_enviar FROM {s}reposicion_sugerida"),
    ("¿Cuántas unidades de talla M sugiere el modelo frente al reparto parejo?",
     "SELECT SUM(unidades_sugeridas) AS modelo, SUM(unidades_reparto_parejo) AS reparto_parejo "
     "FROM {s}reposicion_sugerida WHERE talla = 'M'"),
    ("¿Cómo evolucionó semana a semana la tasa de quiebre en Perú?",
     "SELECT semana, SUM(dias_sku_en_quiebre) / SUM(dias_sku_activos) AS tasa_quiebre "
     "FROM {s}kpi_semanal WHERE pais = 'PE' GROUP BY semana ORDER BY semana"),
]
