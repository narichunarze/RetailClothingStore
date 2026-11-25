"""Gold: modelos de negocio listos para BI, Genie y ML."""

import sys

from pyspark import pipelines as dp

sys.path.append(spark.conf.get("bundle_root"))  # noqa: F821

from src import transforms as T  # noqa: E402


def _t(name):
    return spark.read.table(name)  # noqa: F821


@dp.materialized_view(
    name="gold_daily_sales",
    comment="Ventas y devoluciones por día-tienda-SKU con dimensiones; montos netos en USD "
            "(tipo de cambio fijo de presupuesto).",
    cluster_by=["date", "store_id"],
)
def gold_daily_sales():
    return T.daily_sales(_t("silver_sales"), _t("silver_returns"),
                         _t("silver_products"), _t("silver_stores"))


@dp.materialized_view(
    name="gold_stockout_daily",
    comment="Quiebre de stock por día-tienda-SKU. is_stockout = SKU activo (venta en los 28 "
            "días previos) con on_hand <= 0. lost_units_est = demanda diaria promedio estimada.",
    cluster_by=["date", "store_id"],
)
def gold_stockout_daily():
    return T.stockout_daily(_t("silver_inventory"), _t("gold_daily_sales"),
                            _t("silver_products"), _t("silver_stores"))


@dp.materialized_view(
    name="gold_kpi_weekly",
    comment="KPIs semanales por país, tienda, categoría y talla: tasa de quiebre, ventas y "
            "ventas perdidas estimadas (USD).",
)
def gold_kpi_weekly():
    return T.kpi_weekly(_t("gold_stockout_daily"), _t("gold_daily_sales"))


@dp.materialized_view(
    name="gold_size_curve",
    comment="Participación de cada talla en ventas vs. stock por categoría. "
            "stock_minus_sales_share < 0 indica talla sub-surtida.",
)
def gold_size_curve():
    return T.size_curve(_t("gold_stockout_daily"))
