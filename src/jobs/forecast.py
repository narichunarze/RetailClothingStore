# Databricks notebook source
# MAGIC %md
# MAGIC # Forecast semanal de demanda + sugerencias de reposición
# MAGIC 1. Backtest (últimas N semanas) vs. baselines ingenuos → métricas en MLflow.
# MAGIC 2. Re-entrena con toda la historia y registra el modelo en Unity Catalog.
# MAGIC    Solo recibe el alias `champion` si le gana al mejor baseline.
# MAGIC 3. Predice la próxima semana y escribe `gold_demand_forecast` y
# MAGIC    `gold_replenishment_suggestions`.

# COMMAND ----------

import sys

dbutils.widgets.text("catalog", "workspace")  # noqa: F821
dbutils.widgets.text("schema", "andesmart_dev")  # noqa: F821
dbutils.widgets.text("bundle_root", "")  # noqa: F821
dbutils.widgets.text("test_weeks", "8")  # noqa: F821
catalog = dbutils.widgets.get("catalog")  # noqa: F821
schema = dbutils.widgets.get("schema")  # noqa: F821
test_weeks = int(dbutils.widgets.get("test_weeks"))  # noqa: F821
sys.path.append(dbutils.widgets.get("bundle_root"))  # noqa: F821

import datetime as dt  # noqa: E402

import mlflow  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402

from src.ml import features as FE  # noqa: E402
from src.ml import replenishment as RP  # noqa: E402
from src.ml import train as TR  # noqa: E402


def fq(t):
    return f"`{catalog}`.`{schema}`.`{t}`"


# COMMAND ----------

weekly = spark.table(fq("gold_weekly_demand")).toPandas()  # noqa: F821
holidays = spark.table(fq("silver_holidays")).toPandas()  # noqa: F821
weekly["week_start"] = pd.to_datetime(weekly["week_start"])

complete = weekly[weekly["days"] == 7]
next_week = (complete["week_start"].max() + pd.Timedelta(days=7)).date()
feats = FE.build_features(FE.add_future_week(weekly[weekly["days"] == 7], next_week), holidays)
history = feats[feats["week_start"] < pd.Timestamp(next_week)]
future = feats[feats["week_start"] == pd.Timestamp(next_week)]
print(f"historia: {len(history):,} filas | semana a predecir: {next_week} ({len(future):,} SKUs)")

# COMMAND ----------

user = spark.sql("SELECT current_user()").first()[0]  # noqa: F821
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{user}/andesmart-demand-forecast")
model_name = f"{catalog}.{schema}.demand_forecast"

with mlflow.start_run(run_name=f"weekly-forecast-{next_week}") as run:
    bt = TR.backtest(history, test_weeks)
    m = bt["metrics"]
    best_baseline = min(m["wape_naive_last_week"], m["wape_naive_roll_4"])
    beats_baseline = m["wape_model"] < best_baseline
    mlflow.log_params({**TR.PARAMS, "test_weeks": test_weeks, "features": ",".join(FE.FEATURES),
                       "target": "units_sold + lost_units_est"})
    mlflow.log_metrics({**m, **bt["by_size"], "beats_baseline": int(beats_baseline)})
    print(m)

    model = TR.fit_full(history)
    sample = history[FE.FEATURES].head(200)
    log_kwargs = dict(registered_model_name=model_name, input_example=sample.head(5),
                      signature=infer_signature(sample, model.predict(sample)))
    try:  # MLflow 3 usa `name`; MLflow 2, `artifact_path`
        info = mlflow.sklearn.log_model(model, name="model", **log_kwargs)
    except TypeError:
        info = mlflow.sklearn.log_model(model, artifact_path="model", **log_kwargs)
    version = info.registered_model_version

client = mlflow.MlflowClient()


def current_champion():
    try:
        return client.get_model_version_by_alias(model_name, "champion").version
    except Exception:
        return None


if beats_baseline or current_champion() is None:
    if not beats_baseline:
        print("AVISO: no hay champion previo; se promueve aunque no supere al baseline")
    client.set_registered_model_alias(model_name, "champion", version)
    print(f"{model_name} v{version} -> champion")
else:
    print(f"v{version} NO supera al baseline ({m['wape_model']:.3f} vs {best_baseline:.3f}); "
          "se mantiene el champion anterior")

# COMMAND ----------

# Se predice con el champion vigente (puede ser una versión anterior).
champion = mlflow.sklearn.load_model(f"models:/{model_name}@champion")
champ_version = current_champion()

fc = future[["store_id", "sku", "model_id", "category", "size", "color", "country",
             "list_price_usd", "on_hand_end", "in_transit_end"]].copy()
fc["demand_7d_pred"] = np.clip(champion.predict(future[FE.FEATURES]), 0, None).round(2)
fc = fc.rename(columns={"on_hand_end": "on_hand", "in_transit_end": "in_transit"})
fc["forecast_week_start"] = next_week
fc["model_version"] = int(champ_version)
fc["run_id"] = run.info.run_id
fc["created_at"] = dt.datetime.now(dt.timezone.utc)

spark.createDataFrame(fc).write.mode("overwrite").option(  # noqa: F821
    "overwriteSchema", "true").saveAsTable(fq("gold_demand_forecast"))

sug = RP.suggest(fc)
sug["days_of_cover"] = sug["days_of_cover"].replace(np.inf, np.nan)
spark.createDataFrame(sug).write.mode("overwrite").option(  # noqa: F821
    "overwriteSchema", "true").saveAsTable(fq("gold_replenishment_suggestions"))

print(f"{int(sug['stockout_risk_7d'].sum()):,} SKUs en riesgo; "
      f"{int(sug['suggested_units'].sum()):,} unidades sugeridas")
