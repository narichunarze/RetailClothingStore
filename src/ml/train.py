"""Entrenamiento y evaluación del forecast semanal (scikit-learn, sin dependencias extra).

Modelo global (un solo modelo para todos los SKUs): HistGradientBoosting con pérdida
Poisson, adecuada para conteos con muchos ceros. Siempre se compara contra baselines
ingenuos: si no les gana, no se promueve (ver notebook del job).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from src.ml.features import CAT_FEATURES, FEATURES, NUM_FEATURES, TARGET

PARAMS = {"loss": "poisson", "learning_rate": 0.05, "max_iter": 400, "max_leaf_nodes": 31,
          "min_samples_leaf": 40, "l2_regularization": 1.0, "random_state": 0}


def wape(y: np.ndarray, yhat: np.ndarray) -> float:
    """Weighted Absolute Percentage Error: sum|error| / sum(real). Robusto con ceros."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float(np.abs(y - yhat).sum() / max(y.sum(), 1e-9))


def make_model(params: dict | None = None) -> Pipeline:
    pre = ColumnTransformer(
        [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                                encoded_missing_value=-1), CAT_FEATURES),
         ("num", "passthrough", NUM_FEATURES)],
        verbose_feature_names_out=False,
    )
    mask = [True] * len(CAT_FEATURES) + [False] * len(NUM_FEATURES)
    reg = HistGradientBoostingRegressor(categorical_features=mask, **(params or PARAMS))
    return Pipeline([("pre", pre), ("reg", reg)])


def split_by_time(df: pd.DataFrame, test_weeks: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    weeks = np.sort(df["week_start"].unique())
    cutoff = weeks[-test_weeks]
    return df[df["week_start"] < cutoff], df[df["week_start"] >= cutoff]


def backtest(df: pd.DataFrame, test_weeks: int = 8) -> dict:
    """Entrena con el pasado y evalúa en las últimas `test_weeks` semanas."""
    train, test = split_by_time(df.dropna(subset=[TARGET]), test_weeks)
    model = make_model().fit(train[FEATURES], train[TARGET])
    pred = np.clip(model.predict(test[FEATURES]), 0, None)
    y = test[TARGET].to_numpy()
    metrics = {
        "wape_model": wape(y, pred),
        "wape_naive_last_week": wape(y, test["lag_1"].fillna(0)),
        "wape_naive_roll_4": wape(y, test["roll_4"].fillna(0)),
        "bias_model": float((pred.sum() - y.sum()) / max(y.sum(), 1e-9)),
        "train_rows": len(train),
        "test_rows": len(test),
    }
    # error por talla: ¿el modelo corrige el sesgo en tallas centrales?
    t = test.assign(pred=pred)
    by_size = {f"wape_size_{s}": wape(g[TARGET], g["pred"]) for s, g in t.groupby("size")}
    return {"model": model, "metrics": metrics, "by_size": by_size,
            "test_predictions": t[["store_id", "sku", "week_start", "size", TARGET, "pred"]]}


def fit_full(df: pd.DataFrame) -> Pipeline:
    d = df.dropna(subset=[TARGET])
    return make_model().fit(d[FEATURES], d[TARGET])
