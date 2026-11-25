# Databricks notebook source
# MAGIC %md
# MAGIC # Capa semántica para Genie
# MAGIC Recrea las vistas en español (con comentarios por columna) definidas en `src/semantic.py`.

# COMMAND ----------

import sys

dbutils.widgets.text("catalog", "workspace")  # noqa: F821
dbutils.widgets.text("schema", "andesmart_dev")  # noqa: F821
dbutils.widgets.text("bundle_root", "")  # noqa: F821
catalog = dbutils.widgets.get("catalog")  # noqa: F821
schema = dbutils.widgets.get("schema")  # noqa: F821
sys.path.append(dbutils.widgets.get("bundle_root"))  # noqa: F821

from src import semantic as S  # noqa: E402


def fq(t):
    return f"`{catalog}`.`{schema}`.`{t}`"


class _Tables(dict):
    def __missing__(self, key):
        return fq(key)


# COMMAND ----------

for v in S.VIEWS:
    spark.sql(S.create_view_sql(v, _Tables(), fq(v.name)))  # noqa: F821
    print(f"vista {fq(v.name)} OK")
