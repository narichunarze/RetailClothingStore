"""Backtest contrafactual de la política de reposición.

Simula el mismo negocio (misma demanda, mismas semillas) con cada política y compara
quiebre, fill rate, inventario y venta perdida. Responde la pregunta del negocio:
"¿cuánto mejora si reponemos por curva de tallas en vez de repartir parejo?"

    python -m src.data_gen.backtest_policy --seeds 42 7 123
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

import pandas as pd

from src.data_gen.generate import POLICIES, simulate


def run(seeds: list[int], start: dt.date = dt.date(2025, 1, 1), days: int = 365,
        n_stores: int = 12, n_models: int = 40) -> pd.DataFrame:
    rows = []
    for seed in seeds:
        for policy in POLICIES:
            s = simulate(None, None, start, days, n_stores, n_models, seed, policy=policy)
            by_size = s["stockout_rate_by_size"]
            rows.append({
                "seed": seed, "policy": policy,
                "stockout_rate": s["stockout_rate"], "fill_rate": s["fill_rate"],
                "avg_inventory_units": s["avg_inventory_units"], "lost_units": s["lost_units"],
                "stockout_rate_M": by_size.get("M"), "stockout_rate_XS": by_size.get("XS"),
            })
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Promedio por política y variación vs. la práctica actual (even_split)."""
    mean = df.groupby("policy").mean(numeric_only=True).drop(columns="seed").loc[list(POLICIES)]
    base = mean.loc["even_split"]
    mean["lost_units_vs_current"] = (mean["lost_units"] / base["lost_units"] - 1).round(3)
    mean["inventory_vs_current"] = (mean["avg_inventory_units"]
                                    / base["avg_inventory_units"] - 1).round(3)
    return mean.round(4)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, nargs="+", default=[42, 7, 123])
    p.add_argument("--days", type=int, default=365)
    a = p.parse_args()
    detail = run(a.seeds, days=a.days)
    summary = summarize(detail)
    print(summary.to_string())
    print(json.dumps({"seeds": a.seeds, "days": a.days}))


if __name__ == "__main__":
    main()
