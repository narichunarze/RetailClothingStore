import datetime as dt

import pytest
from pyspark.sql import SparkSession

from src.transforms import dedupe_sales


@pytest.fixture(scope="session")
def spark():
    return SparkSession.builder.master("local[1]").appName("tests").getOrCreate()


def test_dedupe_sales_keeps_latest(spark):
    t1, t2 = dt.datetime(2026, 1, 1, 8), dt.datetime(2026, 1, 1, 9)
    df = spark.createDataFrame(
        [("tx1", 10.0, t1), ("tx1", 12.0, t2), ("tx2", 5.0, t1)],
        ["transaction_id", "amount", "_ingested_at"],
    )
    out = {r.transaction_id: r.amount for r in dedupe_sales(df).collect()}
    assert out == {"tx1": 12.0, "tx2": 5.0}
