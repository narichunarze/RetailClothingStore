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


# --------------------------------------------------------------------------- gold

# Tipo de cambio fijo de presupuesto (moneda local por USD), igual que el generador.
FX_TO_LOCAL = {"PEN": 3.7, "CLP": 950.0, "COP": 4000.0, "MXN": 18.0}
LOOKBACK_DAYS = 28


def _fx_col(currency_col: str = "currency") -> F.Column:
    mapping = F.create_map(*[x for k, v in FX_TO_LOCAL.items() for x in (F.lit(k), F.lit(v))])
    return mapping[F.col(currency_col)]


def daily_sales(sales: DataFrame, returns: DataFrame, products: DataFrame,
                stores: DataFrame) -> DataFrame:
    """Ventas y devoluciones por día-tienda-SKU, con dimensiones y montos en USD."""
    keys = ["date", "store_id", "sku"]
    s = (sales.withColumnRenamed("sale_date", "date").groupBy(keys).agg(
        F.sum("quantity").alias("units_sold"),
        F.sum("net_amount").alias("net_sales_local"),
        F.countDistinct("ticket_id").alias("tickets"),
        F.avg("discount_pct").alias("avg_discount_pct"),
    ))
    r = (returns.withColumnRenamed("return_date", "date").groupBy(keys).agg(
        F.sum("quantity").alias("units_returned"),
        F.sum("refund_amount").alias("refunds_local"),
    ))
    zero = {"units_sold": 0, "net_sales_local": 0, "tickets": 0,
            "units_returned": 0, "refunds_local": 0}
    return (
        s.join(r, keys, "full").fillna(zero)
        .join(stores.select("store_id", "country", "city", "currency"), "store_id")
        .join(products.select("sku", "model_id", "category", "season", "size", "color"), "sku")
        .withColumn("net_units", F.col("units_sold") - F.col("units_returned"))
        .withColumn("net_sales_usd",
                    F.round((F.col("net_sales_local") - F.col("refunds_local")) / _fx_col(), 2))
    )


def stockout_daily(inventory: DataFrame, daily: DataFrame, products: DataFrame,
                   stores: DataFrame, lookback: int = LOOKBACK_DAYS) -> DataFrame:
    """Quiebre de stock por día-tienda-SKU.

    - Completa días sin snapshot (o con `on_hand` negativo, dato inválido) con el último
      valor conocido.
    - SKU "activo" = tuvo venta en los `lookback` días previos. Quiebre = activo y on_hand <= 0.
    - Venta perdida estimada = demanda diaria promedio de los días previos con stock, menos lo
      que sí se vendió ese día (el snapshot es al cierre: el SKU pudo quebrarse a media jornada).
      Validado contra la demanda real del generador en tests/test_gold.py.
    """
    inv = inventory.select(
        F.col("snapshot_date").alias("date"), "store_id", "sku",
        F.when(F.col("on_hand") >= 0, F.col("on_hand")).alias("on_hand_raw"),
        "in_transit",
    )
    bounds = inv.agg(F.min("date").alias("lo"), F.max("date").alias("hi"))
    dates = bounds.select(F.explode(F.sequence("lo", "hi")).alias("date"))
    grid = inv.select("store_id", "sku").distinct().crossJoin(dates)

    w = Window.partitionBy("store_id", "sku").orderBy("date")
    day_n = F.datediff(F.col("date"), F.lit("2000-01-01"))
    w_prev = (Window.partitionBy("store_id", "sku").orderBy(day_n)
              .rangeBetween(-lookback, -1))

    units = daily.select("date", "store_id", "sku", "units_sold")
    df = (
        grid.join(inv, ["date", "store_id", "sku"], "left")
        .join(units, ["date", "store_id", "sku"], "left").fillna({"units_sold": 0})
        .withColumn("snapshot_missing", F.col("on_hand_raw").isNull())
        .withColumn("on_hand", F.last("on_hand_raw", ignorenulls=True).over(
            w.rowsBetween(Window.unboundedPreceding, Window.currentRow)))
        .withColumn("units_prev", F.sum("units_sold").over(w_prev))
        # día "disponible" = cerró con stock o vendió algo (si vendió, hubo stock parte del día)
        .withColumn("in_stock_days_prev",
                    F.sum(F.when((F.col("on_hand") > 0) | (F.col("units_sold") > 0), 1)
                          .otherwise(0)).over(w_prev))
        .withColumn("is_active", F.coalesce(F.col("units_prev"), F.lit(0)) > 0)
        .withColumn("is_stockout", F.col("is_active") & (F.col("on_hand") <= 0))
        .withColumn("avg_daily_demand",
                    F.col("units_prev") / F.greatest(F.col("in_stock_days_prev"), F.lit(1)))
        # si se quebró durante el día, solo se pierde lo que faltó vender
        .withColumn("lost_units_est",
                    F.when(F.col("is_stockout"),
                           F.greatest(F.col("avg_daily_demand") - F.col("units_sold"), F.lit(0.0)))
                    .otherwise(0.0))
        .withColumn("days_of_cover",
                    F.when(F.col("avg_daily_demand") > 0,
                           F.round(F.col("on_hand") / F.col("avg_daily_demand"), 1)))
        .drop("on_hand_raw")
        .join(products.select("sku", "model_id", "category", "season", "size", "color",
                                  "list_price_usd"),
              "sku")
        .join(stores.select("store_id", "country", "city"), "store_id")
        .withColumn("lost_sales_usd_est",
                    F.round(F.col("lost_units_est") * F.col("list_price_usd"), 2))
    )
    return df


def kpi_weekly(stockouts: DataFrame, daily: DataFrame) -> DataFrame:
    """KPIs semanales por país-tienda-categoría-talla (grano del dashboard)."""
    dims = ["week_start", "country", "store_id", "category", "size"]
    so = (stockouts.withColumn("week_start", F.date_trunc("week", "date").cast("date"))
          .groupBy(dims).agg(
              F.sum(F.col("is_active").cast("int")).alias("active_sku_days"),
              F.sum(F.col("is_stockout").cast("int")).alias("stockout_sku_days"),
              F.round(F.sum("lost_units_est"), 1).alias("lost_units_est"),
              F.round(F.sum("lost_sales_usd_est"), 2).alias("lost_sales_usd_est"),
          ))
    sales = (daily.withColumn("week_start", F.date_trunc("week", "date").cast("date"))
             .groupBy(dims).agg(F.sum("units_sold").alias("units_sold"),
                                F.sum("net_sales_usd").alias("net_sales_usd")))
    return (so.join(sales, dims, "left").fillna({"units_sold": 0, "net_sales_usd": 0})
            .withColumn("stockout_rate", F.round(
                F.col("stockout_sku_days") / F.greatest(F.col("active_sku_days"), F.lit(1)), 4)))


def size_curve(stockouts: DataFrame) -> DataFrame:
    """Participación de cada talla en ventas vs. en stock, por categoría.

    `stock_minus_sales_share` < 0 => la talla tiene menos stock del que vende (sub-surtida).
    """
    agg = stockouts.groupBy("category", "size").agg(
        F.sum("units_sold").alias("units_sold"),
        F.avg("on_hand").alias("avg_on_hand"),
        F.avg(F.col("is_stockout").cast("double")).alias("stockout_rate"),
    )
    w = Window.partitionBy("category")
    return (agg
            .withColumn("sales_share", F.round(F.col("units_sold") / F.sum("units_sold").over(w), 4))
            .withColumn("stock_share",
                        F.round(F.col("avg_on_hand") / F.sum("avg_on_hand").over(w), 4))
            .withColumn("stock_minus_sales_share",
                        F.round(F.col("stock_share") - F.col("sales_share"), 4))
            .withColumn("stockout_rate", F.round("stockout_rate", 4)))


def weekly_demand(stockouts: DataFrame, stores: DataFrame) -> DataFrame:
    """Demanda semanal (lunes a domingo) por tienda-SKU: base de entrenamiento del forecast.

    demand = units_sold + lost_units_est. La venta sola está censurada en días de quiebre
    (no se vende lo que no hay); entrenar con ella subestimaría justo las tallas que se quiebran.
    """
    week = F.date_trunc("week", "date").cast("date")
    return (
        stockouts.withColumn("week_start", week)
        .groupBy("store_id", "sku", "week_start")
        .agg(
            F.count("*").alias("days"),
            F.first("model_id").alias("model_id"),
            F.first("category").alias("category"),
            F.first("season").alias("season"),
            F.first("size").alias("size"),
            F.first("color").alias("color"),
            F.first("country").alias("country"),
            # double (no decimal): pandas convierte decimal a objetos Decimal lentos e incompatibles
            F.first("list_price_usd").cast("double").alias("list_price_usd"),
            F.sum("units_sold").alias("units_sold"),
            F.round(F.sum("lost_units_est"), 2).alias("lost_units_est"),
            F.sum(F.col("is_stockout").cast("int")).alias("stockout_days"),
            F.max_by("on_hand", "date").alias("on_hand_end"),
            F.max_by("in_transit", "date").alias("in_transit_end"),
        )
        .withColumn("demand", F.round(F.col("units_sold") + F.col("lost_units_est"), 2))
        .join(stores.select("store_id", "hemisphere"), "store_id")
    )
