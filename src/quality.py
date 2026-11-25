"""Quality gate: reglas que deciden si los datos de la corrida se pueden publicar.

Lógica pura (sin Spark) para poder testearla; el notebook del job solo junta las métricas.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_QUARANTINE_SHARE = 0.01     # > 1% de ventas rechazadas => algo cambió en la fuente
MAX_STOCKOUT_RATE = 0.30        # una tasa absurda suele indicar inventario mal cargado
REQUIRED_NON_EMPTY = ["silver_sales", "silver_inventory", "gold_daily_sales",
                      "gold_stockout_daily", "gold_kpi_weekly", "gold_size_curve"]


@dataclass
class Metrics:
    row_counts: dict[str, int]
    sales_quarantine_rows: int
    stockout_rate: float | None


def evaluate(m: Metrics) -> list[str]:
    """Devuelve la lista de fallos (vacía = OK)."""
    failures = []
    for t in REQUIRED_NON_EMPTY:
        if m.row_counts.get(t, 0) == 0:
            failures.append(f"{t} está vacía")

    valid = m.row_counts.get("silver_sales", 0)
    total = valid + m.sales_quarantine_rows
    if total and m.sales_quarantine_rows / total > MAX_QUARANTINE_SHARE:
        failures.append(
            f"cuarentena de ventas = {m.sales_quarantine_rows / total:.2%} "
            f"(máx. {MAX_QUARANTINE_SHARE:.0%})")

    if m.stockout_rate is None:
        failures.append("no se pudo calcular la tasa de quiebre")
    elif not 0 <= m.stockout_rate <= MAX_STOCKOUT_RATE:
        failures.append(f"tasa de quiebre fuera de rango: {m.stockout_rate:.2%}")
    return failures
