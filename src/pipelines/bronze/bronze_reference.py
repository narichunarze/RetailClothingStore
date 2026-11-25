"""Bronze: maestros y datos externos.

Son archivos pequeños que se reemplazan completos (no se acumulan), por eso se leen en batch
como vistas materializadas en vez de con Auto Loader.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

RAW = spark.conf.get("raw_path")  # noqa: F821


def _batch(fmt: str, path: str, **options):
    return (
        spark.read.format(fmt)  # noqa: F821
        .options(**options)
        .load(f"{RAW}/{path}")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dp.materialized_view(name="bronze_products", comment="Maestro de productos (PIM).")
def bronze_products():
    return _batch("csv", "master/products.csv", header="true")


@dp.materialized_view(name="bronze_stores", comment="Maestro de tiendas (ERP).")
def bronze_stores():
    return _batch("csv", "master/stores.csv", header="true")


@dp.materialized_view(name="bronze_weather", comment="Clima diario por ciudad (Open-Meteo).")
def bronze_weather():
    # recursiveFileLookup evita que Spark infiera `city` desde la carpeta city=<x>,
    # que chocaría con la columna `city` del JSON.
    return _batch("json", "weather", recursiveFileLookup="true")


@dp.materialized_view(name="bronze_holidays", comment="Feriados por país (Nager.Date).")
def bronze_holidays():
    return _batch("json", "holidays", recursiveFileLookup="true", multiLine="true")
