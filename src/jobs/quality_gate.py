# Databricks notebook source
# MAGIC %md
# MAGIC # Quality gate
# MAGIC Corre después del pipeline. Si falla, el job queda en rojo y las tareas siguientes
# MAGIC (forecast, refresh del dashboard) no se ejecutan. Reglas en `src/quality.py`.

# COMMAND ----------

import sys

dbutils.widgets.text("catalog", "workspace")  # noqa: F821
dbutils.widgets.text("schema", "andesmart_dev")  # noqa: F821
dbutils.widgets.text("bundle_root", "")  # noqa: F821
catalog = dbutils.widgets.get("catalog")  # noqa: F821
schema = dbutils.widgets.get("schema")  # noqa: F821
sys.path.append(dbutils.widgets.get("bundle_root"))  # noqa: F821

from src import quality as Q  # noqa: E402

# COMMAND ----------


def fq(table: str) -> str:
    return f"`{catalog}`.`{schema}`.`{table}`"


counts = {t: spark.table(fq(t)).count() for t in Q.REQUIRED_NON_EMPTY}  # noqa: F821
quarantine = spark.table(fq("silver_sales_quarantine")).count()  # noqa: F821
rate = spark.sql(  # noqa: F821
    f"SELECT SUM(stockout_sku_days) / SUM(active_sku_days) AS r FROM {fq('gold_kpi_weekly')}"
).first()["r"]

metrics = Q.Metrics(row_counts=counts, sales_quarantine_rows=quarantine,
                    stockout_rate=float(rate) if rate is not None else None)
print(metrics)

failures = Q.evaluate(metrics)
if failures:
    raise Exception("Quality gate FALLÓ:\n- " + "\n- ".join(failures))
print("Quality gate OK")
