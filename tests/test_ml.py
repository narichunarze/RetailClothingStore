"""Tests del forecast y la reposición (pandas + sklearn, sin Spark)."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.ml import features as FE
from src.ml import replenishment as RP
from src.ml import train as TR

START = dt.date(2025, 1, 6)  # lunes


def _weekly(n_weeks=30, seed=0, n_stores=2):
    """Demanda semanal sintética: tallas centrales venden más, con estacionalidad leve."""
    rng = np.random.default_rng(seed)
    rows = []
    for store in [f"S{i}" for i in range(1, n_stores + 1)]:
        for size, mult in [("S", 1.0), ("M", 3.0), ("L", 2.0)]:
            for w in range(n_weeks):
                lam = mult * (4 + 2 * np.sin(w / 4))
                rows.append({
                    "store_id": store, "sku": f"M1-NEG-{size}", "model_id": "M1", "color": "negro",
                    "size": size, "category": "jeans", "season": "all", "country": "PE",
                    "hemisphere": "S", "list_price_usd": 40.0, "days": 7,
                    "week_start": pd.Timestamp(START + dt.timedelta(weeks=w)),
                    "demand": float(rng.poisson(lam)), "units_sold": 0, "lost_units_est": 0,
                    "stockout_days": 0, "on_hand_end": 10, "in_transit_end": 0,
                })
    return pd.DataFrame(rows)


def test_wape():
    assert TR.wape([10, 0, 10], [10, 5, 5]) == pytest.approx(0.5)


def test_lags_do_not_leak_current_week():
    f = FE.build_features(_weekly())
    one = f[(f.store_id == "S1") & (f.size == "M")].sort_values("week_start")
    prev = one["demand"].shift(1)
    assert (one["lag_1"].iloc[1:].to_numpy() == prev.iloc[1:].to_numpy()).all()
    # roll_4 de la semana t = promedio de t-1..t-4, nunca incluye t
    raw = _weekly()
    s = raw[(raw.store_id == "S1") & (raw.size == "M")].sort_values("week_start")["demand"]
    expected = s.shift(1).rolling(4).mean().dropna().to_numpy()
    assert np.allclose(one["roll_4"].to_numpy(), expected)


def test_future_week_gets_features_but_no_target():
    w = _weekly(12)
    nxt = (w.week_start.max() + pd.Timedelta(days=7)).date()
    f = FE.build_features(FE.add_future_week(w, nxt))
    fut = f[f.week_start == pd.Timestamp(nxt)]
    assert len(fut) == 6 and fut["demand"].isna().all() and fut["lag_1"].notna().all()


def test_calendar_features_use_known_business_calendar():
    w = _weekly(50)
    f = FE.build_features(w)
    mothers_week = f[f.week_start == pd.Timestamp("2025-05-05")]  # Día de la Madre: 11 may
    assert (mothers_week["event_days"] > 0).all()


def test_backtest_beats_naive_baseline():
    f = FE.build_features(_weekly(40, n_stores=25))
    bt = TR.backtest(f, test_weeks=8)
    m = bt["metrics"]
    assert m["wape_model"] < m["wape_naive_last_week"]
    assert set(bt["by_size"]) == {"wape_size_S", "wape_size_M", "wape_size_L"}


def test_replenishment_policy():
    fc = pd.DataFrame({
        "store_id": ["S1"] * 3, "sku": ["a-S", "a-M", "a-L"], "model_id": ["a"] * 3,
        "color": ["negro"] * 3, "size": ["S", "M", "L"], "list_price_usd": [40.0] * 3,
        "demand_7d_pred": [7.0, 21.0, 0.0], "on_hand": [10, 2, 5], "in_transit": [0, 0, np.nan],
    })
    s = RP.suggest(fc).set_index("size")
    # M: cubre 10 días (30) + seguridad 1.65*sqrt(30)≈9 => 40 - 2 = 38
    assert s.loc["M", "suggested_units"] == 38
    assert s.loc["M", "stockout_risk_7d"] and not s.loc["S", "stockout_risk_7d"]
    assert s.loc["L", "suggested_units"] == 0
    # el reparto parejo le daría a M bastante menos de lo que necesita
    assert s.loc["M", "delta_vs_even_split"] > 0 > s.loc["S", "delta_vs_even_split"]
    assert s.index[0] == "M"  # ordenado por venta en riesgo
