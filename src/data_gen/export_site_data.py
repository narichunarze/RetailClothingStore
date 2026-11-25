"""Exporta los datos de la página de portafolio (site/data.json).

Corre el backtest de políticas con el simulador y junta los resultados ya medidos en el
proyecto (forecast, estimador, Genie). Determinístico: misma salida con las mismas semillas.

    python -m src.data_gen.export_site_data --out site/data.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from src.data_gen.backtest_policy import run, summarize
from src.data_gen.config import APPAREL_SIZES
from src.data_gen.generate import POLICIES, simulate

START = dt.date(2025, 1, 1)
DAYS = 365
CHART_SEED = 42
SUMMARY_SEEDS = [42, 7, 123]

# Resultados medidos en otras partes del proyecto (ver docs/07, docs/08 y tests/test_gold.py).
MEASURED = {
    "forecast_wape": [
        {"level": "store_sku", "model": 0.48, "naive_last_week": 0.62, "naive_roll_4": 0.52},
        {"level": "store_model_color", "model": 0.27, "naive_last_week": 0.40, "naive_roll_4": 0.33},
        {"level": "country_category", "model": 0.16, "naive_last_week": 0.32, "naive_roll_4": 0.26},
    ],
    "lost_sales_estimator_error": {"first_version": 0.60, "final": 0.08},
    "genie_benchmarks": {"iterations": [6, 9, 10, 12], "total": 12},
    "tests": 47,
}


def build(start: dt.date = START, days: int = DAYS, chart_seed: int = CHART_SEED,
          summary_seeds: list[int] | None = None, n_stores: int = 12,
          n_models: int = 40) -> dict:
    seeds = summary_seeds or SUMMARY_SEEDS
    policies = {}
    for policy in POLICIES:
        s = simulate(None, None, start, days, n_stores, n_models, chart_seed, policy=policy)
        policies[policy] = {
            "stockout_rate": s["stockout_rate"],
            "fill_rate": s["fill_rate"],
            "lost_units": s["lost_units"],
            "avg_inventory_units": s["avg_inventory_units"],
            "by_size": {k: s["by_size"][k] for k in APPAREL_SIZES if k in s["by_size"]},
            "weekly": s["weekly"],
        }

    # Curva de tallas (ropa) bajo la práctica actual: participación en venta vs. en stock.
    cur = policies["even_split"]["by_size"]
    demand = {k: v["units_sold"] + v["lost_units"] for k, v in cur.items()}
    tot_d, tot_s = sum(demand.values()), sum(v["avg_on_hand"] for v in cur.values())
    size_curve = [{"size": k, "demand_share": round(demand[k] / tot_d, 4),
                   "stock_share": round(cur[k]["avg_on_hand"] / tot_s, 4),
                   "stockout_rate": cur[k]["stockout_rate"]} for k in cur]

    summary = summarize(run(seeds, start=start, days=days, n_stores=n_stores,
                            n_models=n_models))
    return {
        "generated_at": dt.date.today().isoformat(),
        "setup": {"stores": n_stores, "countries": 4, "models": n_models, "days": days,
                  "chart_seed": chart_seed, "summary_seeds": seeds},
        "policies": policies,
        "size_curve": size_curve,
        "summary": {p: {k: float(v) for k, v in row.items()}
                    for p, row in summary.to_dict(orient="index").items()},
        "measured": MEASURED,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("site/data.json"))
    a = p.parse_args()
    data = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"escrito {a.out} ({a.out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
