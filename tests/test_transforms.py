"""Tests de la lógica Silver sobre datos reales del generador, leídos como en Bronze (strings)."""

import datetime as dt
import json

import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from src import transforms as T
from src.data_gen.generate import Quality, simulate


@pytest.fixture(scope="session")
def spark():
    return (SparkSession.builder.master("local[2]").appName("tests")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.sql.session.timeZone", "UTC").getOrCreate())


@pytest.fixture(scope="module")
def raw(tmp_path_factory):
    root = tmp_path_factory.mktemp("raw")
    # tasas de error altas para que aparezcan en una muestra chica
    q = Quality(duplicate_rate=0.05, negative_price_rate=0.02, null_store_rate=0.02)
    simulate(root, None, dt.date(2025, 3, 1), 20, n_stores=3, n_models=8, seed=3, quality=q)
    return root


def _bronze(spark, fmt, path, **opts):
    """Imita Bronze: todo string + metadatos de ingesta."""
    return (spark.read.format(fmt).options(**opts).load(str(path))
            .withColumn("_ingested_at", F.current_timestamp())
            .withColumn("_source_file", F.col("_metadata.file_path")))


@pytest.fixture(scope="module")
def sales_cleaned(spark, raw):
    bronze = _bronze(spark, "csv", raw / "sales", header="true", inferSchema="false")
    return T.with_failed_rules(T.clean_sales(bronze), T.SALES_RULES).cache()


def test_dedupe_latest_keeps_most_recent(spark):
    t1, t2 = dt.datetime(2026, 1, 1, 8), dt.datetime(2026, 1, 1, 9)
    df = spark.createDataFrame(
        [("tx1", 10.0, t1), ("tx1", 12.0, t2), ("tx2", 5.0, t1)],
        ["transaction_id", "amount", "_ingested_at"],
    )
    out = {r.transaction_id: r.amount for r in T.dedupe_latest(df, ["transaction_id"]).collect()}
    assert out == {"tx1": 12.0, "tx2": 5.0}


def test_failed_rules_lists_every_broken_rule(spark):
    df = spark.createDataFrame(
        [(None, "A", -1.0, 1, "x"), ("S1", "A", 5.0, 0, "x"), ("S1", "A", 5.0, 1, "x")],
        "store_id string, sku string, unit_price double, quantity int, sold_at string",
    )
    rows = T.with_failed_rules(df, T.SALES_RULES).orderBy("quantity", "unit_price").collect()
    by_case = {(r.store_id, r.unit_price, r.quantity): sorted(r.failed_rules) for r in rows}
    assert by_case[(None, -1.0, 1)] == ["valid_price", "valid_store"]
    assert by_case[("S1", 5.0, 0)] == ["valid_quantity"]
    assert by_case[("S1", 5.0, 1)] == []


def test_clean_sales_types_and_sku_normalization(sales_cleaned):
    types = dict(sales_cleaned.dtypes)
    assert types["sold_at"] == "timestamp"
    assert types["sale_date"] == "date"
    assert types["quantity"] == "int"
    assert types["unit_price"].startswith("decimal")
    assert sales_cleaned.where(F.col("sku") != F.upper("sku")).count() == 0


def test_rules_catch_injected_issues(sales_cleaned):
    failed = sales_cleaned.select(F.explode("failed_rules").alias("r")).distinct()
    found = {r.r for r in failed.collect()}
    assert {"valid_store", "valid_price"} <= found
    assert sales_cleaned.where(F.size("failed_rules") > 0).count() < 0.1 * sales_cleaned.count()


def test_silver_sales_has_unique_transactions(sales_cleaned):
    valid = sales_cleaned.where(T.all_rules_pass(T.SALES_RULES))
    silver = T.dedupe_latest(valid, ["transaction_id"])
    assert valid.count() > silver.count()  # había re-envíos
    assert silver.select("transaction_id").distinct().count() == silver.count()


def test_clean_inventory_and_returns(spark, raw):
    inv = T.clean_inventory(_bronze(spark, "json", raw / "inventory"))
    assert dict(inv.dtypes)["on_hand"] == "int"
    assert inv.where("snapshot_date IS NULL").count() == 0
    ret = T.clean_returns(_bronze(spark, "csv", raw / "returns", header="true"))
    assert ret.count() > 0 and dict(ret.dtypes)["return_date"] == "date"


def test_masters(spark, raw):
    p = T.clean_products(_bronze(spark, "csv", raw / "master" / "products.csv", header="true"))
    s = T.clean_stores(_bronze(spark, "csv", raw / "master" / "stores.csv", header="true"))
    assert p.select("sku").distinct().count() == p.count()
    assert s.count() == 3


def test_explode_weather(spark, tmp_path):
    payload = {"city": "Lima", "country": "PE", "daily": {
        "time": ["2025-01-01", "2025-01-02"], "temperature_2m_mean": [23.1, 24.0],
        "temperature_2m_max": [27.0, 28.2], "precipitation_sum": [0.0, 0.3]}}
    (tmp_path / "w.json").write_text(json.dumps(payload))
    out = T.explode_weather(spark.read.json(str(tmp_path / "w.json"))).orderBy("weather_date")
    rows = out.collect()
    assert len(rows) == 2 and rows[1].temp_mean_c == 24.0 and str(rows[0].weather_date) == "2025-01-01"


def test_clean_holidays_dedupes(spark):
    df = spark.createDataFrame(
        [("PE", "2025-07-28", "Fiestas Patrias", "Independence Day")] * 2,
        "countryCode string, date string, localName string, name string",
    )
    assert T.clean_holidays(df).count() == 1
