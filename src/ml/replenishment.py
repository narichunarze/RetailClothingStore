"""Sugerencia de reposición tienda-SKU a partir del forecast semanal.

Política de revisión periódica: cada lunes se pide para cubrir el lead time (3 días, llega
el jueves) más el período hasta la próxima revisión (7 días), con stock de seguridad.
Demanda ~ Poisson => desviación estándar ≈ sqrt(media).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LEAD_TIME_DAYS = 3
REVIEW_DAYS = 7
SERVICE_Z = 1.65   # ~95% de nivel de servicio


def suggest(fc: pd.DataFrame, lead_time_days: int = LEAD_TIME_DAYS,
            review_days: int = REVIEW_DAYS, z: float = SERVICE_Z) -> pd.DataFrame:
    """`fc` necesita: store_id, sku, model_id, color, size, demand_7d_pred, on_hand,
    in_transit, list_price_usd."""
    df = fc.copy()
    df["on_hand"] = df["on_hand"].fillna(0).clip(lower=0)
    df["in_transit"] = df["in_transit"].fillna(0).clip(lower=0)
    daily = df["demand_7d_pred"] / 7
    cover = daily * (lead_time_days + review_days)
    safety = z * np.sqrt(cover)
    position = df["on_hand"] + df["in_transit"]

    df["target_stock"] = np.ceil(cover + safety)
    df["suggested_units"] = (df["target_stock"] - position).clip(lower=0).astype(int)
    df["days_of_cover"] = np.where(daily > 0, (position / daily).round(1), np.inf)
    df["stockout_risk_7d"] = position < df["demand_7d_pred"]
    df["at_risk_sales_usd"] = ((df["demand_7d_pred"] - position).clip(lower=0)
                               * df["list_price_usd"]).round(2)

    # Comparación con la práctica actual: el mismo total por modelo-color repartido igual
    # entre tallas. La diferencia por talla es el valor del modelo para el negocio.
    grp = ["store_id", "model_id", "color"]
    total = df.groupby(grp)["suggested_units"].transform("sum")
    n = df.groupby(grp)["sku"].transform("count")
    df["even_split_units"] = np.floor(total / n).astype(int)
    df["delta_vs_even_split"] = df["suggested_units"] - df["even_split_units"]
    return df.sort_values("at_risk_sales_usd", ascending=False).reset_index(drop=True)
