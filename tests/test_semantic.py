"""La capa semántica y los benchmarks de Genie corren sobre las tablas Gold reales (locales)."""

import numpy as np
import pandas as pd
import pytest

from src import semantic as S
from src import transforms as T
from src.ml import features as FE
from src.ml import replenishment as RP
from src.ml import train as TR


@pytest.fixture(scope="module")
def views(spark, medallion_full):
    m = medallion_full
    so, daily, stores = m["stockouts"], m["daily"], m["stores"]

    # forecast + reposición como en el job
    weekly = T.weekly_demand(so, stores).toPandas()
    weekly["week_start"] = pd.to_datetime(weekly["week_start"])
    c = weekly[weekly.days == 7]
    nxt = (c.week_start.max() + pd.Timedelta(days=7)).date()
    f = FE.build_features(FE.add_future_week(c, nxt))
    hist, fut = f[f.week_start < pd.Timestamp(nxt)], f[f.week_start == pd.Timestamp(nxt)]
    fc = fut[["store_id", "sku", "model_id", "category", "size", "color", "country",
              "list_price_usd", "on_hand_end", "in_transit_end"]].rename(
        columns={"on_hand_end": "on_hand", "in_transit_end": "in_transit"})
    fc["demand_7d_pred"] = np.clip(TR.fit_full(hist).predict(fut[FE.FEATURES]), 0, None)
    fc["forecast_week_start"] = nxt
    fc["model_version"] = 1
    sug = RP.suggest(fc)
    sug["days_of_cover"] = sug["days_of_cover"].replace(np.inf, np.nan)

    tables = {
        "silver_stores": stores,
        "gold_kpi_weekly": T.kpi_weekly(so, daily),
        "gold_stockout_daily": so,
        "gold_size_curve": T.size_curve(so),
        "gold_replenishment_suggestions": spark.createDataFrame(sug),
    }
    for name, df in tables.items():
        df.createOrReplaceTempView(name)
    for v in S.VIEWS:
        spark.sql(S.create_view_sql(v, {k: k for k in tables}, v.name, temp=True))
    return spark


def test_every_view_has_documented_columns(views):
    for v in S.VIEWS:
        cols = views.table(v.name).columns
        assert cols == [a for a, _, _ in v.columns]
        assert all(c for _, _, c in v.columns), f"columna sin comentario en {v.name}"
        assert views.table(v.name).count() > 0


@pytest.mark.parametrize("question,sql", S.BENCHMARKS, ids=[q[:40] for q, _ in S.BENCHMARKS])
def test_benchmark_sql_runs(views, question, sql):
    rows = views.sql(sql.format(s="")).collect()
    assert rows is not None


def test_benchmark_answers_tell_the_size_story(views):
    top_size = views.sql(S.BENCHMARKS[1][1].format(s="")).first()["talla"]
    assert top_size in {"M", "L"}
    r = views.sql(S.BENCHMARKS[8][1].format(s="")).first()
    assert r["modelo"] > r["reparto_parejo"]
