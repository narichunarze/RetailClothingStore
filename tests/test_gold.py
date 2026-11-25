"""Tests de Gold: lógica de quiebre (casos chicos) y validación end-to-end contra la verdad."""

import datetime as dt

import pandas as pd
import pytest
from pyspark.sql import functions as F

from src import transforms as T
from src.data_gen.generate import simulate

D = dt.date(2025, 1, 1)


def _day(i):
    return D + dt.timedelta(days=i)


@pytest.fixture(scope="module")
def dims(spark):
    products = spark.createDataFrame(
        [("A-M", "A", "jeans", "all", "M", "negro", 40.0)],
        "sku string, model_id string, category string, season string, size string, "
        "color string, list_price_usd double")
    stores = spark.createDataFrame([("S1", "PE", "Lima")], "store_id string, country string, city string")
    return products, stores


def _stockouts(spark, dims, inv_rows, sales_rows):
    products, stores = dims
    inv = spark.createDataFrame(
        [(_day(i), "S1", "A-M", oh, 0) for i, oh in inv_rows],
        "snapshot_date date, store_id string, sku string, on_hand int, in_transit int")
    daily = spark.createDataFrame(
        [(_day(i), "S1", "A-M", u) for i, u in sales_rows],
        "date date, store_id string, sku string, units_sold long")
    out = T.stockout_daily(inv, daily, products, stores).orderBy("date").collect()
    return {(r.date - D).days: r for r in out}


def test_stockout_requires_recent_sales(spark, dims):
    # sin ventas previas, on_hand 0 no es quiebre (SKU inactivo)
    rows = _stockouts(spark, dims, [(0, 0), (1, 0)], [])
    assert not rows[1].is_stockout


def test_stockout_and_lost_sales_estimate(spark, dims):
    # vende 2/día con stock los días 0–3; día 4 queda en 0 -> quiebre, pierde ~2 unidades
    inv = [(0, 8), (1, 6), (2, 4), (3, 2), (4, 0)]
    sales = [(0, 2), (1, 2), (2, 2), (3, 2)]
    rows = _stockouts(spark, dims, inv, sales)
    assert rows[4].is_stockout
    assert rows[4].lost_units_est == pytest.approx(2.0)
    assert rows[4].lost_sales_usd_est == pytest.approx(80.0)
    assert not rows[3].is_stockout


def test_missing_and_negative_snapshots_are_forward_filled(spark, dims):
    # día 1 sin snapshot, día 2 con on_hand negativo (dato inválido) -> usar 5
    rows = _stockouts(spark, dims, [(0, 5), (2, -5), (3, 4)], [(0, 1)])
    assert rows[1].snapshot_missing and rows[1].on_hand == 5
    assert rows[2].on_hand == 5
    assert rows[3].on_hand == 4


@pytest.fixture(scope="module")
def medallion(spark, tmp_path_factory):
    """Corre Silver + Gold localmente sobre 120 días generados."""
    root = tmp_path_factory.mktemp("e2e")
    simulate(root / "raw", root / "truth", D, 120, n_stores=3, n_models=8, seed=11)
    raw = root / "raw"

    def bronze(fmt, path, **o):
        return (spark.read.format(fmt).options(**o).load(str(raw / path))
                .withColumn("_ingested_at", F.current_timestamp()))

    sales = T.dedupe_latest(
        T.clean_sales(bronze("csv", "sales", header="true").withColumn("_source_file", F.lit("")))
        .where(T.all_rules_pass(T.SALES_RULES)), ["transaction_id"])
    returns = T.clean_returns(bronze("csv", "returns", header="true")
                              .withColumn("_source_file", F.lit("")))
    inv = T.clean_inventory(bronze("json", "inventory").withColumn("_source_file", F.lit("")))
    products = T.clean_products(bronze("csv", "master/products.csv", header="true"))
    stores = T.clean_stores(bronze("csv", "master/stores.csv", header="true"))
    daily = T.daily_sales(sales, returns, products, stores).cache()
    so = T.stockout_daily(inv, daily, products, stores).cache()
    truth = pd.read_csv(root / "truth" / "lost_sales.csv.gz")
    return daily, so, truth


def test_central_sizes_are_undersupplied(medallion):
    _, so, _ = medallion
    curve = {(r.category, r.size): r for r in T.size_curve(so).collect()}
    jeans_m, jeans_xs = curve[("jeans", "M")], curve[("jeans", "XS")]
    assert jeans_m.stockout_rate > jeans_xs.stockout_rate
    assert jeans_m.stock_minus_sales_share < 0 < jeans_xs.stock_minus_sales_share


def test_lost_sales_estimate_is_close_to_truth(medallion):
    """La estimación no ve la demanda real; validamos contra la verdad del generador."""
    _, so, truth = medallion
    est = so.agg(F.sum("lost_units_est")).first()[0]
    real = truth["lost_units"].sum()
    print(f"lost units est={est:.0f} real={real} ratio={est / real:.2f}")
    assert 0.7 * real < est < 1.3 * real, (est, real)


def test_weekly_demand_uncensors_sales(spark, medallion):
    _, so, _ = medallion
    stores = spark.createDataFrame([(s, "S") for s in ["S001", "S002", "S003"]],
                                   "store_id string, hemisphere string")
    w = T.weekly_demand(so, stores)
    r = w.agg(F.sum("units_sold").alias("u"), F.sum("lost_units_est").alias("l"),
              F.sum("demand").alias("d"), F.max("days").alias("days")).first()
    assert r.d == pytest.approx(r.u + r.l, rel=1e-3) and r.l > 0 and r.days == 7


def test_kpi_weekly_rates_are_valid(medallion):
    daily, so, _ = medallion
    k = T.kpi_weekly(so, daily)
    assert k.where("stockout_rate < 0 OR stockout_rate > 1").count() == 0
    assert k.agg(F.sum("units_sold")).first()[0] == daily.agg(F.sum("units_sold")).first()[0]
