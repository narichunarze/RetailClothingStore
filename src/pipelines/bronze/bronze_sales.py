"""Bronze: ingesta incremental (Auto Loader) de los archivos crudos, tal cual llegan.

Todo se lee como string (sin inferir tipos): Bronze no interpreta, solo conserva.
Columnas que no calzan con el esquema quedan en `_rescued_data` en lugar de perderse.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

RAW = spark.conf.get("raw_path")  # noqa: F821  (`spark` lo inyecta el runtime del pipeline)


def _autoloader(fmt: str, subdir: str, **options):
    reader = (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", fmt)
        .option("cloudFiles.inferColumnTypes", "false")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
    )
    for k, v in options.items():
        reader = reader.option(k, v)
    return (
        reader.load(f"{RAW}/{subdir}/")
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )


@dp.table(name="bronze_sales", comment="Líneas de ticket del POS (CSV diario), crudas.")
def bronze_sales():
    return _autoloader("csv", "sales", header="true")


@dp.table(name="bronze_returns", comment="Devoluciones del POS (CSV diario), crudas.")
def bronze_returns():
    return _autoloader("csv", "returns", header="true")


@dp.table(name="bronze_inventory",
          comment="Snapshots de inventario del ERP al cierre (JSON lines gzip), crudos.")
def bronze_inventory():
    return _autoloader("json", "inventory")
