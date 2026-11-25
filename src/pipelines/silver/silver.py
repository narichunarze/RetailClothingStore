"""Silver: tipos correctos, normalización, deduplicación y reglas de calidad.

- Las filas que no cumplen las reglas se descartan (expect_all_or_drop) y quedan registradas
  en las métricas del pipeline.
- Además se guardan en tablas *_quarantine con el motivo, para que negocio/TI las revise.
- La lógica vive en `src/transforms.py` (testeada con pytest).
"""

import sys

from pyspark import pipelines as dp
from pyspark.sql import functions as F

sys.path.append(spark.conf.get("bundle_root"))  # noqa: F821  hace importable `src.*`

from src import transforms as T  # noqa: E402

# --------------------------------------------------------------------------- ventas


@dp.temporary_view(name="sales_cleaned")
def sales_cleaned():
    return T.with_failed_rules(T.clean_sales(spark.read.table("bronze_sales")),  # noqa: F821
                               T.SALES_RULES)


@dp.materialized_view(
    name="silver_sales",
    comment="Líneas de venta válidas y deduplicadas (una fila por transaction_id).",
    cluster_by=["sale_date", "store_id"],
)
@dp.expect_all_or_drop(T.SALES_RULES)
def silver_sales():
    df = spark.read.table("sales_cleaned").drop("failed_rules")  # noqa: F821
    return T.dedupe_latest(df, ["transaction_id"])


@dp.materialized_view(name="silver_sales_quarantine",
                      comment="Líneas de venta rechazadas por reglas de calidad, con el motivo.")
def silver_sales_quarantine():
    return spark.read.table("sales_cleaned").where(F.size("failed_rules") > 0)  # noqa: F821


# --------------------------------------------------------------------------- devoluciones


@dp.temporary_view(name="returns_cleaned")
def returns_cleaned():
    return T.with_failed_rules(
        T.clean_returns(spark.read.table("bronze_returns")), T.RETURNS_RULES  # noqa: F821
    )


@dp.materialized_view(name="silver_returns", comment="Devoluciones válidas y deduplicadas.")
@dp.expect_all_or_drop(T.RETURNS_RULES)
def silver_returns():
    df = spark.read.table("returns_cleaned").drop("failed_rules")  # noqa: F821
    return T.dedupe_latest(df, ["return_id"])


@dp.materialized_view(name="silver_returns_quarantine",
                      comment="Devoluciones rechazadas por reglas de calidad, con el motivo.")
def silver_returns_quarantine():
    return spark.read.table("returns_cleaned").where(F.size("failed_rules") > 0)  # noqa: F821


# --------------------------------------------------------------------------- inventario


@dp.materialized_view(
    name="silver_inventory",
    comment="Snapshot de inventario al cierre por tienda-SKU-día.",
    cluster_by=["snapshot_date", "store_id"],
)
@dp.expect_all(T.INVENTORY_WARN_RULES)
def silver_inventory():
    df = T.clean_inventory(spark.read.table("bronze_inventory"))  # noqa: F821
    return T.dedupe_latest(df, ["snapshot_date", "store_id", "sku"])


# --------------------------------------------------------------------------- maestros y externos


@dp.materialized_view(name="silver_products", comment="Productos: un SKU por modelo-color-talla.")
@dp.expect_or_fail("unique_sku_not_null", "sku IS NOT NULL")
def silver_products():
    return T.clean_products(spark.read.table("bronze_products")).dropDuplicates(["sku"])  # noqa: F821


@dp.materialized_view(name="silver_stores", comment="Tiendas.")
@dp.expect_or_fail("store_id_not_null", "store_id IS NOT NULL")
def silver_stores():
    return T.clean_stores(spark.read.table("bronze_stores")).dropDuplicates(["store_id"])  # noqa: F821


@dp.materialized_view(name="silver_weather", comment="Clima diario por ciudad.")
def silver_weather():
    return T.explode_weather(spark.read.table("bronze_weather"))  # noqa: F821


@dp.materialized_view(name="silver_holidays", comment="Feriados por país.")
def silver_holidays():
    return T.clean_holidays(spark.read.table("bronze_holidays"))  # noqa: F821
