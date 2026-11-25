"""Features para el forecast semanal de demanda (pandas).

Cada fila = (tienda, SKU, semana objetivo). Todas las features usan solo información
disponible el lunes en que se decide la reposición:
- historia de demanda hasta la semana anterior (lags), y
- calendario comercial conocido de antemano (eventos, feriados, temporada, liquidaciones).
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from src.data_gen import calendar_effects as ce

KEYS = ["store_id", "sku"]
CAT_FEATURES = ["store_id", "category", "size", "color", "country", "hemisphere"]
NUM_FEATURES = [
    "lag_1", "lag_2", "roll_4", "roll_8", "stockout_days_lag_1",
    "sku_share_of_model_color", "model_color_roll_4", "category_country_roll_4",
    "week_of_year", "month", "event_days", "holiday_days", "in_season_frac", "markdown_pct",
    "list_price_usd",
]
FEATURES = CAT_FEATURES + NUM_FEATURES
TARGET = "demand"


def add_future_week(weekly: pd.DataFrame, week_start: dt.date) -> pd.DataFrame:
    """Agrega una fila sin demanda (a predecir) para cada tienda-SKU en `week_start`."""
    last = weekly.sort_values("week_start").groupby(KEYS, as_index=False).last()
    future = last.assign(week_start=pd.Timestamp(week_start), days=7, demand=np.nan,
                         units_sold=np.nan, lost_units_est=np.nan, stockout_days=np.nan)
    return pd.concat([weekly, future], ignore_index=True)


def _calendar_features(weeks: pd.DataFrame, holidays: pd.DataFrame | None) -> pd.DataFrame:
    """Features de calendario por (semana, país, hemisferio, temporada de la categoría)."""
    hol = set()
    if holidays is not None and len(holidays):
        hol = {(c, pd.Timestamp(d).date()) for c, d in
               zip(holidays["country"], holidays["holiday_date"])}
    events_cache: dict[tuple[int, str], dict] = {}
    rows = []
    for w, country, hemi, season in weeks.itertuples(index=False):
        days = [pd.Timestamp(w).date() + dt.timedelta(days=i) for i in range(7)]
        ev = 0
        for d in days:
            key = (d.year, country)
            if key not in events_cache:
                events_cache[key] = ce.commercial_events(d.year, country)
            ev += events_cache[key].get(d, 1.0) > 1.0
        rows.append({
            "week_start": w, "country": country, "hemisphere": hemi, "season": season,
            "event_days": ev,
            "holiday_days": sum((country, d) in hol for d in days),
            "in_season_frac": float(np.mean([
                season == "all" or ce.season_of(d, hemi) == season for d in days])),
            "markdown_pct": float(np.mean([ce.markdown_pct(season, d, hemi) for d in days])),
        })
    return pd.DataFrame(rows)


def build_features(weekly: pd.DataFrame, holidays: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabla de features. Descarta semanas incompletas y las primeras 4 de cada SKU (sin lags)."""
    df = weekly[weekly["days"] == 7].copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    num_cols = ["demand", "units_sold", "lost_units_est", "stockout_days", "list_price_usd",
                "on_hand_end", "in_transit_end"]
    df[num_cols] = df[num_cols].apply(pd.to_numeric, errors="coerce").astype(float)
    df = df.sort_values(KEYS + ["week_start"]).reset_index(drop=True)

    g = df.groupby(KEYS)[TARGET]
    df["lag_1"] = g.shift(1)
    df["lag_2"] = g.shift(2)
    df["roll_4"] = g.transform(lambda s: s.shift(1).rolling(4).mean())
    df["roll_8"] = g.transform(lambda s: s.shift(1).rolling(8, min_periods=4).mean())
    df["stockout_days_lag_1"] = df.groupby(KEYS)["stockout_days"].shift(1)

    # Nivel modelo-color en la tienda: la talla hereda la tendencia del modelo
    mc_keys = ["store_id", "model_id", "color"]
    mc = (df.groupby(mc_keys + ["week_start"], as_index=False)[TARGET].sum(min_count=1)
          .sort_values(mc_keys + ["week_start"]))
    mc["model_color_roll_4"] = (mc.groupby(mc_keys)[TARGET]
                                .transform(lambda s: s.shift(1).rolling(4).mean()))
    df = df.merge(mc[mc_keys + ["week_start", "model_color_roll_4"]],
                  on=mc_keys + ["week_start"], how="left")
    df["sku_share_of_model_color"] = (df["roll_4"] / df["model_color_roll_4"]).fillna(0)

    # Tendencia de la categoría en el país
    cc_keys = ["country", "category"]
    cc = (df.groupby(cc_keys + ["week_start"], as_index=False)[TARGET].sum(min_count=1)
          .sort_values(cc_keys + ["week_start"]))
    cc["category_country_roll_4"] = (cc.groupby(cc_keys)[TARGET]
                                     .transform(lambda s: s.shift(1).rolling(4).mean()))
    df = df.merge(cc[cc_keys + ["week_start", "category_country_roll_4"]],
                  on=cc_keys + ["week_start"], how="left")

    weeks = df[["week_start", "country", "hemisphere", "season"]].drop_duplicates()
    df = df.merge(_calendar_features(weeks, holidays),
                  on=["week_start", "country", "hemisphere", "season"], how="left")
    df["week_of_year"] = df["week_start"].dt.isocalendar().week.astype(int)
    df["month"] = df["week_start"].dt.month

    return df.dropna(subset=["roll_4"]).reset_index(drop=True)
