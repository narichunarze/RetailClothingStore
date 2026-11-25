"""Entry points de las tareas del job (python_wheel_task).

El código se instala como wheel desde un Volume de Unity Catalog, en lugar de importarse
desde los archivos del workspace: la lectura vía FUSE de `/Workspace/.../.bundle` da
`OSError: [Errno 5] Input/output error` de forma intermitente (ver ADR-0004).

Cada función recibe parámetros como `--catalog=... --schema=...` (named_parameters del job).
"""

from __future__ import annotations

import argparse
import datetime as dt


def _args(*extra: tuple[str, str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", default="workspace")
    p.add_argument("--schema", default="andesmart_dev")
    for name, default in extra:
        p.add_argument(f"--{name}", default=default)
    a, _ = p.parse_known_args()
    return a


def _spark():
    from pyspark.sql import SparkSession

    return SparkSession.builder.getOrCreate()


def _fq(a: argparse.Namespace, table: str) -> str:
    return f"`{a.catalog}`.`{a.schema}`.`{table}`"


# --------------------------------------------------------------------------- quality gate


def quality_gate() -> None:
    from src import quality as Q

    a, spark = _args(), _spark()
    counts = {t: spark.table(_fq(a, t)).count() for t in Q.REQUIRED_NON_EMPTY}
    quarantine = spark.table(_fq(a, "silver_sales_quarantine")).count()
    rate = spark.sql(
        f"SELECT SUM(stockout_sku_days) / SUM(active_sku_days) AS r "
        f"FROM {_fq(a, 'gold_kpi_weekly')}").first()["r"]
    metrics = Q.Metrics(row_counts=counts, sales_quarantine_rows=quarantine,
                        stockout_rate=float(rate) if rate is not None else None)
    print(metrics)
    failures = Q.evaluate(metrics)
    if failures:
        raise RuntimeError("Quality gate FALLÓ:\n- " + "\n- ".join(failures))
    print("Quality gate OK")


# --------------------------------------------------------------------------- forecast


def forecast() -> None:
    import mlflow
    import numpy as np
    import pandas as pd
    from mlflow.models import infer_signature

    from src.ml import features as FE
    from src.ml import replenishment as RP
    from src.ml import train as TR

    a, spark = _args(("test_weeks", "8")), _spark()
    test_weeks = int(a.test_weeks)

    weekly = spark.table(_fq(a, "gold_weekly_demand")).toPandas()
    holidays = spark.table(_fq(a, "silver_holidays")).toPandas()
    weekly["week_start"] = pd.to_datetime(weekly["week_start"])
    complete = weekly[weekly["days"] == 7]
    next_week = (complete["week_start"].max() + pd.Timedelta(days=7)).date()
    feats = FE.build_features(FE.add_future_week(complete, next_week), holidays)
    history = feats[feats["week_start"] < pd.Timestamp(next_week)]
    future = feats[feats["week_start"] == pd.Timestamp(next_week)]
    print(f"historia: {len(history):,} filas | semana a predecir: {next_week} "
          f"({len(future):,} SKUs)")

    user = spark.sql("SELECT current_user()").first()[0]
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(f"/Users/{user}/andesmart-demand-forecast")
    model_name = f"{a.catalog}.{a.schema}.demand_forecast"
    client = mlflow.MlflowClient()

    def current_champion():
        try:
            return client.get_model_version_by_alias(model_name, "champion").version
        except Exception:
            return None

    with mlflow.start_run(run_name=f"weekly-forecast-{next_week}") as run:
        bt = TR.backtest(history, test_weeks)
        m = bt["metrics"]
        best_baseline = min(m["wape_naive_last_week"], m["wape_naive_roll_4"])
        beats_baseline = m["wape_model"] < best_baseline
        mlflow.log_params({**TR.PARAMS, "test_weeks": test_weeks,
                           "features": ",".join(FE.FEATURES),
                           "target": "units_sold + lost_units_est"})
        mlflow.log_metrics({**m, **bt["by_size"], "beats_baseline": int(beats_baseline)})
        print(m)

        model = TR.fit_full(history)
        sample = history[FE.FEATURES].head(200)
        kwargs = dict(registered_model_name=model_name, input_example=sample.head(5),
                      signature=infer_signature(sample, model.predict(sample)))
        try:  # MLflow 3 usa `name`; MLflow 2, `artifact_path`
            info = mlflow.sklearn.log_model(model, name="model", **kwargs)
        except TypeError:
            info = mlflow.sklearn.log_model(model, artifact_path="model", **kwargs)
        version = info.registered_model_version

    if beats_baseline or current_champion() is None:
        if not beats_baseline:
            print("AVISO: no hay champion previo; se promueve aunque no supere al baseline")
        client.set_registered_model_alias(model_name, "champion", version)
        print(f"{model_name} v{version} -> champion")
    else:
        print(f"v{version} NO supera al baseline ({m['wape_model']:.3f} vs "
              f"{best_baseline:.3f}); se mantiene el champion anterior")

    champion = mlflow.sklearn.load_model(f"models:/{model_name}@champion")
    fc = future[["store_id", "sku", "model_id", "category", "size", "color", "country",
                 "list_price_usd", "on_hand_end", "in_transit_end"]].copy()
    fc["demand_7d_pred"] = np.clip(champion.predict(future[FE.FEATURES]), 0, None).round(2)
    fc = fc.rename(columns={"on_hand_end": "on_hand", "in_transit_end": "in_transit"})
    fc["forecast_week_start"] = next_week
    fc["model_version"] = int(current_champion())
    fc["run_id"] = run.info.run_id
    fc["created_at"] = dt.datetime.now(dt.timezone.utc)

    (spark.createDataFrame(fc).write.mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(_fq(a, "gold_demand_forecast")))
    sug = RP.suggest(fc)
    sug["days_of_cover"] = sug["days_of_cover"].replace(np.inf, np.nan)
    (spark.createDataFrame(sug).write.mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(_fq(a, "gold_replenishment_suggestions")))
    print(f"{int(sug['stockout_risk_7d'].sum()):,} SKUs en riesgo; "
          f"{int(sug['suggested_units'].sum()):,} unidades sugeridas")


# --------------------------------------------------------------------------- capa semántica


def semantic_layer() -> None:
    from src import semantic as S

    a, spark = _args(("reader_group", "account users")), _spark()

    class _Tables(dict):
        def __missing__(self, key):
            return _fq(a, key)

    for v in S.VIEWS:
        spark.sql(S.create_view_sql(v, _Tables(), _fq(a, v.name)))
        print(f"vista {_fq(a, v.name)} OK")

    # Mínimo privilegio: el grupo de negocio solo lee las vistas, no las tablas base.
    grants = [f"GRANT USE SCHEMA ON SCHEMA `{a.catalog}`.`{a.schema}` TO `{a.reader_group}`"]
    grants += [f"GRANT SELECT ON VIEW {_fq(a, v.name)} TO `{a.reader_group}`" for v in S.VIEWS]
    for g in grants:
        try:
            spark.sql(g)
            print("OK  ", g)
        except Exception as e:  # p. ej. el grupo no existe en este workspace
            print("SKIP", g, "->", str(e).splitlines()[0])
