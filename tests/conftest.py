import datetime as dt

import pandas as pd
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from src import transforms as T
from src.data_gen.generate import simulate

D = dt.date(2025, 1, 1)


@pytest.fixture(scope="session")
def spark():
    return (SparkSession.builder.master("local[2]").appName("tests")
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.sql.session.timeZone", "UTC").getOrCreate())


@pytest.fixture(scope="session")
def medallion_full(spark, tmp_path_factory):
    """Corre Silver + Gold localmente sobre 120 días generados (compartido entre tests)."""
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
    return {"daily": daily, "stockouts": so, "truth": truth, "stores": stores,
            "products": products}


@pytest.fixture(scope="session")
def medallion(medallion_full):
    m = medallion_full
    return m["daily"], m["stockouts"], m["truth"]
