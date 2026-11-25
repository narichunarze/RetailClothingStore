"""Lógica de negocio como funciones PySpark puras (testeables con pytest). Ver ADR-0002."""

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def dedupe_sales(df: DataFrame) -> DataFrame:
    """Elimina duplicados del POS quedándose con el registro ingerido más reciente."""
    w = Window.partitionBy("transaction_id").orderBy(F.col("_ingested_at").desc())
    return df.withColumn("_rn", F.row_number().over(w)).filter("_rn = 1").drop("_rn")
