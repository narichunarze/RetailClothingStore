"""Bronze: ingesta incremental de ventas POS (CSV) con Auto Loader. Implementar en Fase 2."""

from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(name="bronze_sales", comment="Ventas POS crudas, tal cual llegan.")
def bronze_sales():
    raw_path = spark.conf.get("raw_path")  # noqa: F821 (spark lo inyecta el runtime)
    return (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(f"{raw_path}/sales/")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )
