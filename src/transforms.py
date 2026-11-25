"""Lógica de negocio como funciones PySpark puras (testeables con pytest). Ver ADR-0002.

Los pipelines en `src/pipelines/` solo leen/escriben tablas e invocan estas funciones.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

# --------------------------------------------------------------------------- reglas de calidad
# Formato {nombre_regla: condición SQL que debe cumplirse}. Se usan en dp.expect_all_*
# y para construir la tabla de cuarentena con el motivo de rechazo.

SALES_RULES = {
    "valid_store": "store_id IS NOT NULL",
    "valid_sku": "sku IS NOT NULL",
    "valid_price": "unit_price >= 0",
    "valid_quantity": "quantity > 0",
    "valid_timestamp": "sold_at IS NOT NULL",
}

RETURNS_RULES = {
    "valid_store": "store_id IS NOT NULL",
    "valid_quantity": "quantity > 0",
    "valid_transaction": "transaction_id IS NOT NULL",
}

# Solo advertencia: se conserva la fila pero queda registrada en las métricas del pipeline.
INVENTORY_WARN_RULES = {
    "non_negative_on_hand": "on_hand >= 0",
}


def all_rules_pass(rules: dict[str, str]) -> str:
    return " AND ".join(f"({c})" for c in rules.values())


def with_failed_rules(df: DataFrame, rules: dict[str, str]) -> DataFrame:
    """Agrega `failed_rules` (array con los nombres de las reglas que la fila no cumple).

    Un NULL en la condición cuenta como fallo, igual que en las expectations de Lakeflow.
    """
    checks = [F.when(~F.coalesce(F.expr(cond), F.lit(False)), F.lit(name))
              for name, cond in rules.items()]
    return df.withColumn("failed_rules", F.filter(F.array(*checks), lambda x: x.isNotNull()))


# --------------------------------------------------------------------------- utilidades


def dedupe_latest(df: DataFrame, keys: list[str], order_col: str = "_ingested_at") -> DataFrame:
    """Deja una fila por clave: la ingerida más recientemente (re-envíos del POS)."""
    w = Window.partitionBy(*keys).orderBy(F.col(order_col).desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")


def _norm_sku(col: str = "sku") -> F.Column:
    return F.upper(F.trim(F.col(col)))


# --------------------------------------------------------------------------- limpieza por fuente


def clean_sales(df: DataFrame) -> DataFrame:
    """Bronze (todo string) -> tipos de negocio. No filtra: eso lo hacen las reglas."""
    return df.select(
        F.col("transaction_id"),
        F.col("ticket_id"),
        F.nullif(F.trim("store_id"), F.lit("")).alias("store_id"),
        _norm_sku().alias("sku"),
        F.to_timestamp("sold_at", "yyyy-MM-dd HH:mm:ss").alias("sold_at"),
        F.to_date(F.to_timestamp("sold_at", "yyyy-MM-dd HH:mm:ss")).alias("sale_date"),
        F.col("quantity").cast("int").alias("quantity"),
        F.col("unit_price").cast("decimal(14,2)").alias("unit_price"),
        F.col("discount_pct").cast("decimal(4,2)").alias("discount_pct"),
        F.col("net_amount").cast("decimal(14,2)").alias("net_amount"),
        F.col("currency"),
        F.col("payment_method"),
        F.col("_ingested_at"),
        F.col("_source_file"),
    )


def clean_returns(df: DataFrame) -> DataFrame:
    return df.select(
        F.col("return_id"),
        F.col("transaction_id"),
        F.nullif(F.trim("store_id"), F.lit("")).alias("store_id"),
        _norm_sku().alias("sku"),
        F.col("quantity").cast("int").alias("quantity"),
        F.col("reason"),
        F.col("refund_amount").cast("decimal(14,2)").alias("refund_amount"),
        F.col("currency"),
        F.to_date("returned_at").alias("return_date"),
        F.col("_ingested_at"),
        F.col("_source_file"),
    )


def clean_inventory(df: DataFrame) -> DataFrame:
    return df.select(
        F.to_date("snapshot_date").alias("snapshot_date"),
        F.col("store_id"),
        _norm_sku().alias("sku"),
        F.col("on_hand").cast("int").alias("on_hand"),
        F.col("in_transit").cast("int").alias("in_transit"),
        F.col("_ingested_at"),
        F.col("_source_file"),
    )


def clean_products(df: DataFrame) -> DataFrame:
    return df.select(
        _norm_sku().alias("sku"),
        "model_id", "model_name", "category", "season", "color",
        F.col("size").cast("string").alias("size"),
        F.col("list_price_usd").cast("decimal(10,2)").alias("list_price_usd"),
    )


def clean_stores(df: DataFrame) -> DataFrame:
    return df.select(
        "store_id", "store_name", "country", "city",
        F.col("latitude").cast("double").alias("latitude"),
        F.col("longitude").cast("double").alias("longitude"),
        "currency", "hemisphere", "store_format",
    )


def explode_weather(df: DataFrame) -> DataFrame:
    """Open-Meteo trae arrays paralelos en `daily`; se convierten a una fila por ciudad-día."""
    zipped = F.arrays_zip(
        F.col("daily.time").alias("time"),
        F.col("daily.temperature_2m_mean").alias("temp_mean"),
        F.col("daily.temperature_2m_max").alias("temp_max"),
        F.col("daily.precipitation_sum").alias("precipitation"),
    )
    return (
        df.select("city", "country", F.explode(zipped).alias("d"))
        .select(
            "city", "country",
            F.to_date("d.time").alias("weather_date"),
            F.col("d.temp_mean").cast("double").alias("temp_mean_c"),
            F.col("d.temp_max").cast("double").alias("temp_max_c"),
            F.col("d.precipitation").cast("double").alias("precipitation_mm"),
        )
    )


def clean_holidays(df: DataFrame) -> DataFrame:
    return df.select(
        F.col("countryCode").alias("country"),
        F.to_date("date").alias("holiday_date"),
        F.col("localName").alias("holiday_name"),
        F.col("name").alias("holiday_name_en"),
    ).dropDuplicates(["country", "holiday_date"])
