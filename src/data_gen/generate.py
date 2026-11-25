"""Generador de datos sintéticos para AndesMart (retail de ropa).

Simula día a día la demanda por tienda × SKU (modelo-color-talla), el inventario y una
reposición semanal "ciega a la talla" (el planner reparte por igual entre tallas), que es la
causa de negocio de los quiebres en tallas centrales y el sobre-stock en tallas extremas.

Salida (formato "tal cual llega" de los sistemas fuente, con problemas de calidad inyectados):

    <out>/master/products.csv, stores.csv
    <out>/sales/date=YYYY-MM-DD/sales.csv           (POS, líneas de ticket)
    <out>/returns/date=YYYY-MM-DD/returns.csv       (devoluciones)
    <out>/inventory/date=YYYY-MM-DD/inventory.jsonl.gz  (snapshot ERP al cierre)
    <truth>/lost_sales.csv.gz                       (demanda no atendida; NO se ingesta,
                                                     solo para evaluar la solución)

Uso:
    python -m src.data_gen.generate --out data/raw --truth data/truth
    # en Databricks: --out /Volumes/workspace/andesmart_dev/raw
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_gen import calendar_effects as ce
from src.data_gen import config as cfg

CLOSED_DAYS = {(1, 1), (12, 25)}  # tiendas cerradas
MAX_RETURN_LAG = 14
DEMAND_SCALE = 6.0      # calibra el volumen total (~1.000–1.500 unidades/día con defaults)
COVER_DAYS = 21         # cobertura objetivo del planner
MIN_DISPLAY = 2         # stock mínimo de exhibición por SKU


@dataclass
class Quality:
    """Tasas de problemas de calidad inyectados a propósito (para Silver/expectations)."""

    duplicate_rate: float = 0.005      # líneas re-enviadas en el archivo del día siguiente
    negative_price_rate: float = 0.001
    null_store_rate: float = 0.002
    lowercase_sku_rate: float = 0.003
    missing_inventory_rate: float = 0.01   # tienda-día sin snapshot de inventario
    negative_on_hand_rate: float = 0.0005


# --------------------------------------------------------------------------- maestros


def build_stores(rng: np.random.Generator, n_stores: int) -> pd.DataFrame:
    cities = [(c, *city) for c, (_, _, cl) in cfg.COUNTRIES.items() for city in cl]
    rows = []
    for i in range(n_stores):
        country, city, lat, lon = cities[i % len(cities)]
        currency, hemisphere, _ = cfg.COUNTRIES[country]
        rows.append({
            "store_id": f"S{i + 1:03d}",
            "store_name": f"AndesMart {city} {i // len(cities) + 1}",
            "country": country,
            "city": city,
            "latitude": lat,
            "longitude": lon,
            "currency": currency,
            "hemisphere": hemisphere,
            "store_format": rng.choice(["mall", "calle", "outlet"], p=[0.6, 0.3, 0.1]),
            "size_factor": round(float(rng.lognormal(0, 0.35)), 3),
        })
    return pd.DataFrame(rows)


def build_products(rng: np.random.Generator, n_models: int) -> pd.DataFrame:
    cats = list(cfg.CATEGORIES)
    rows = []
    for m in range(n_models):
        cat = cats[m % len(cats)]
        season, (pmin, pmax), sizes, rel = cfg.CATEGORIES[cat]
        model_id = f"M{m + 1:03d}"
        price = round(float(rng.uniform(pmin, pmax)), 2)
        popularity = float(rng.lognormal(0, 0.5)) * rel
        colors = rng.choice(cfg.COLORS, size=int(rng.integers(2, 5)), replace=False)
        for color in colors:
            for size in sizes:
                rows.append({
                    "sku": f"{model_id}-{color[:3].upper()}-{size}",
                    "model_id": model_id,
                    "model_name": f"{cat.capitalize()} {model_id}",
                    "category": cat,
                    "season": season,
                    "color": str(color),
                    "size": size,
                    "list_price_usd": price,
                    "_popularity": popularity,
                })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- externos


def load_temperatures(weather_dir: Path | None, stores: pd.DataFrame,
                      dates: list[dt.date]) -> dict[str, np.ndarray]:
    """Temperatura media diaria por ciudad: Open-Meteo si existe, si no, sintética."""
    out = {}
    for city, lat in stores[["city", "latitude"]].drop_duplicates().itertuples(index=False):
        series = None
        f = weather_dir / f"city={city}" / "weather.json" if weather_dir else None
        if f and f.exists():
            daily = json.loads(f.read_text())["daily"]
            by_date = dict(zip(daily["time"], daily["temperature_2m_mean"]))
            series = [by_date.get(d.isoformat()) for d in dates]
        if series is None or any(v is None for v in series):
            series = [ce.synthetic_temperature(d, lat) for d in dates]
        out[city] = np.asarray(series, dtype=float)
    return out


def load_holidays(holidays_dir: Path | None) -> set[tuple[str, str]]:
    """{(country, 'YYYY-MM-DD')} desde los JSON de Nager.Date, si existen."""
    result: set[tuple[str, str]] = set()
    if not holidays_dir or not holidays_dir.exists():
        return result
    for f in holidays_dir.glob("country=*/*.json"):
        country = f.parent.name.split("=", 1)[1]
        for h in json.loads(f.read_text()):
            result.add((country, h["date"]))
    return result


# --------------------------------------------------------------------------- simulación


POLICIES = ("even_split", "size_curve", "size_aware")


def simulate(out: Path | None, truth: Path | None, start: dt.date, days: int, n_stores: int,
             n_models: int, seed: int, weather_dir: Path | None = None,
             holidays_dir: Path | None = None, quality: Quality | None = None,
             policy: str = "even_split") -> dict:
    """Simula el negocio día a día.

    `policy` = cómo repone el planner cada lunes (ver docs/09-policy-backtest.md):
      - even_split: práctica actual; venta del modelo-color repartida igual entre tallas.
      - size_curve: mismo total, repartido según la curva de tallas observada.
      - size_aware: total con demanda sin censura (venta + perdida) y curva observada,
                    como hace la solución (forecast + venta perdida estimada).
    `out=None` no escribe archivos (útil para backtests).
    """
    if policy not in POLICIES:
        raise ValueError(f"policy debe ser una de {POLICIES}")
    rng = np.random.default_rng(seed)
    # RNG separados: la demanda y la reposición no dependen del resto de la simulación,
    # así distintas políticas enfrentan exactamente la misma demanda.
    demand_rng = np.random.default_rng([seed, 1])
    policy_rng = np.random.default_rng([seed, 2])
    q = quality or Quality()
    dates = [start + dt.timedelta(days=i) for i in range(days)]

    stores = build_stores(rng, n_stores)
    products = build_products(rng, n_models)

    # Surtido: cada tienda vende ~75% de los modelos (todas sus tallas/colores).
    models = products["model_id"].unique()
    carried = {s: set(rng.choice(models, size=int(len(models) * 0.75), replace=False))
               for s in stores["store_id"]}
    pairs = (stores[["store_id"]].merge(products, how="cross")
             .loc[lambda d: [m in carried[s] for s, m in zip(d.store_id, d.model_id)]]
             .merge(stores, on="store_id").reset_index(drop=True))
    P = len(pairs)

    # Componentes fijos de la demanda por par tienda-SKU.
    size_share = pairs["size"].map(cfg.SIZE_CURVE).to_numpy()
    color_w = pairs["color"].map(cfg.COLOR_WEIGHT).to_numpy()
    n_colors = pairs.groupby(["store_id", "model_id"])["color"].transform("nunique").to_numpy()
    base = (DEMAND_SCALE * pairs["_popularity"].to_numpy() * size_share * color_w / n_colors
            * pairs["size_factor"].to_numpy())
    fx = pairs["currency"].map(cfg.FX_TO_LOCAL).to_numpy()
    list_price_local = np.round(pairs["list_price_usd"].to_numpy() * fx, 0)
    cat_season = pairs["season"].to_numpy()
    hemis = pairs["hemisphere"].to_numpy()
    country = pairs["country"].to_numpy()
    city = pairs["city"].to_numpy()
    return_p = cfg.RETURN_RATE * np.where(pairs["category"].isin(["vestidos", "calzado"]), 1.5, 1)

    temps = load_temperatures(weather_dir, stores, dates)
    holidays = load_holidays(holidays_dir)
    events = {(c, d): f for c in cfg.COUNTRIES for y in {d.year for d in dates}
              for d, f in ce.commercial_events(y, c).items()}

    # Grupo de reposición: el planner decide por tienda-modelo-color y reparte igual por talla.
    group = pairs.groupby(["store_id", "model_id", "color"]).ngroup().to_numpy()
    group_size = np.bincount(group)[group]

    def even_split(need: np.ndarray) -> np.ndarray:
        total = np.bincount(group, weights=need)
        return np.floor(total[group] / group_size)

    on_hand = np.maximum(even_split(base * COVER_DAYS), MIN_DISPLAY).astype(float)
    in_transit = np.zeros((4, P))                  # llegadas en t+0..t+3
    returns_queue = np.zeros((MAX_RETURN_LAG + 1, P))
    recent_sales = np.zeros((14, P))
    recent_demand = np.zeros((14, P))
    cum_demand = np.zeros(P)
    on_hand_sum = 0.0
    stockout_days = np.zeros(P)
    active_days = np.zeros(P)
    returns_buffer: list[pd.DataFrame] = []
    pending_dupes: pd.DataFrame | None = None
    lost_rows = []
    stats = {"sales_lines": 0, "units": 0, "lost_units": 0, "returns": 0, "inventory_rows": 0,
             "demand_units": 0}

    for t, d in enumerate(dates):
        ds = d.isoformat()
        # 1) llegadas y devoluciones que vuelven a stock
        on_hand += in_transit[0] + returns_queue[0]
        in_transit = np.roll(in_transit, -1, axis=0)
        in_transit[-1] = 0
        returns_queue = np.roll(returns_queue, -1, axis=0)
        returns_queue[-1] = 0

        # 2) demanda esperada del día
        if (d.month, d.day) in CLOSED_DAYS:
            lam = np.zeros(P)
        else:
            season_f = np.array([ce.season_factor(s, d, h) for s, h in zip(cat_season, hemis)])
            temp_f = np.array([ce.temperature_factor(s, temps[c][t])
                               for s, c in zip(cat_season, city)])
            event_f = np.array([events.get((c, d), 1.0) for c in country])
            hol_f = np.array([1.15 if (c, ds) in holidays else 1.0 for c in country])
            markdown = np.array([ce.markdown_pct(s, d, h) for s, h in zip(cat_season, hemis)])
            bf_promo = 0.2 if event_f.max() > 2 and d.month == 11 else 0.0
            discount = np.maximum(markdown, bf_promo)
            lam = (base * cfg.WEEKDAY_FACTOR[d.weekday()] * season_f * temp_f * event_f
                   * hol_f * (1 + 1.5 * discount))
        demand = demand_rng.poisson(lam)
        sales = np.minimum(demand, np.maximum(on_hand, 0)).astype(int)
        lost = demand - sales
        on_hand -= sales
        recent_sales = np.roll(recent_sales, -1, axis=0)
        recent_sales[-1] = sales
        recent_demand = np.roll(recent_demand, -1, axis=0)
        recent_demand[-1] = demand
        cum_demand += demand
        stats["demand_units"] += int(demand.sum())

        # 3) reposición semanal (lunes): llega el jueves; disponibilidad del CD limitada
        if d.weekday() == 0 and t >= 7:
            # El planner mira la venta del modelo-color (no por talla), proyecta 3 semanas y
            # reparte el pedido en partes iguales entre tallas -> sesgo de curva de tallas.
            basis = recent_demand if policy == "size_aware" else recent_sales
            group_total = np.bincount(group, weights=basis.mean(axis=0))[group]
            if policy == "even_split":
                share = 1 / group_size
            else:  # curva observada (con suavizado hacia el reparto parejo)
                group_cum = np.bincount(group, weights=cum_demand)[group]
                share = (cum_demand + 1) / (group_cum + group_size)
            target = (group_total * share * COVER_DAYS * 1.15
                      * policy_rng.lognormal(0, 0.15, P))
            target = np.maximum(target, MIN_DISPLAY)
            need = np.maximum(target - on_hand - in_transit.sum(axis=0), 0)
            dc_avail = policy_rng.uniform(0.75, 1.0, size=group.max() + 1)[group]
            in_transit[3] += np.ceil(need * dc_avail)

        # 4) líneas POS
        idx = np.nonzero(sales)[0]
        if len(idx):
            single = rng.random(len(idx)) < 0.1  # 10%: una línea con qty=unidades
            rep = np.where(single, 1, sales[idx])
            line_pair = np.repeat(idx, rep)
            qty = np.where(np.repeat(single, rep), np.repeat(sales[idx], rep), 1)
            disc = np.repeat(discount[idx], rep) if lam.any() else np.zeros(len(line_pair))
            n = len(line_pair)
            order = np.lexsort((rng.random(n), pairs["store_id"].to_numpy()[line_pair]))
            line_pair, qty, disc = line_pair[order], qty[order], disc[order]
            store_ids = pairs["store_id"].to_numpy()[line_pair]
            # agrupar líneas en tickets de 1–4 líneas dentro de cada tienda
            new_ticket = np.r_[True, store_ids[1:] != store_ids[:-1]] | (rng.random(n) < 0.55)
            ticket_no = np.cumsum(new_ticket)
            hours = rng.choice(np.arange(10, 22), size=ticket_no.max() + 1,
                               p=np.array([3, 4, 5, 6, 6, 5, 5, 6, 8, 9, 8, 5]) / 70)[ticket_no]
            minutes = rng.integers(0, 60, size=ticket_no.max() + 1)[ticket_no]
            unit_price = list_price_local[line_pair]
            df = pd.DataFrame({
                "transaction_id": [f"{s}-{d:%Y%m%d}-{i:06d}" for i, s in enumerate(store_ids)],
                "ticket_id": [f"T{s}-{d:%Y%m%d}-{k:05d}" for s, k in zip(store_ids, ticket_no)],
                "store_id": store_ids,
                "sold_at": [f"{ds} {h:02d}:{m:02d}:00" for h, m in zip(hours, minutes)],
                "sku": pairs["sku"].to_numpy()[line_pair],
                "quantity": qty,
                "unit_price": unit_price,
                "discount_pct": np.round(disc, 2),
                "net_amount": np.round(qty * unit_price * (1 - disc), 2),
                "currency": pairs["currency"].to_numpy()[line_pair],
                "payment_method": rng.choice(cfg.PAYMENT_METHODS, size=n, p=cfg.PAYMENT_WEIGHTS),
            })

            # devoluciones: vuelven a stock con 1–14 días de rezago (salvo defecto)
            is_ret = rng.random(n) < return_p[line_pair]
            if is_ret.any():
                r = df[is_ret].copy()
                lag = rng.integers(1, MAX_RETURN_LAG + 1, size=len(r))
                r["reason"] = rng.choice(cfg.RETURN_REASONS, size=len(r),
                                         p=cfg.RETURN_REASON_WEIGHTS)
                r["returned_at"] = [(d + dt.timedelta(days=int(k))).isoformat() for k in lag]
                restock = r["reason"].to_numpy() != "defecto"
                np.add.at(returns_queue, (lag[restock], line_pair[is_ret][restock]),
                          qty[is_ret][restock])
                returns_buffer.append(r)

            stats["sales_lines"] += n
            stats["units"] += int(qty.sum())
            df = _inject_sales_issues(df, rng, q)
            if pending_dupes is not None:
                df = pd.concat([df, pending_dupes], ignore_index=True)
            pending_dupes = df.sample(frac=q.duplicate_rate, random_state=int(rng.integers(1e9)))
            if out is not None:
                _write_csv(df, out / "sales" / f"date={ds}" / "sales.csv")

        # 5) devoluciones registradas hoy
        if out is not None:
            _flush_returns(returns_buffer, ds, out, stats)
        else:
            returns_buffer.clear()

        # 6) snapshot de inventario al cierre (JSON lines, gzip)
        if out is not None:
            _write_inventory(pairs, on_hand, in_transit, ds, out, rng, q, stats)

        # métricas de negocio (para comparar políticas): SKU activo = demanda en 14 días
        active = recent_demand.sum(axis=0) > 0
        active_days += active
        stockout_days += active & (on_hand <= 0)
        on_hand_sum += float(np.maximum(on_hand, 0).sum())

        # 7) verdad de terreno: demanda perdida
        if truth is not None and lost.any():
            li = np.nonzero(lost)[0]
            lost_rows.append(pd.DataFrame({"date": ds, "store_id": pairs["store_id"].to_numpy()[li],
                                           "sku": pairs["sku"].to_numpy()[li],
                                           "lost_units": lost[li]}))
        stats["lost_units"] += int(lost.sum())

    # maestros
    if out is not None:
        _write_csv(products.drop(columns="_popularity"), out / "master" / "products.csv")
        _write_csv(stores.drop(columns="size_factor"), out / "master" / "stores.csv")
    if truth is not None and lost_rows:
        truth.mkdir(parents=True, exist_ok=True)
        pd.concat(lost_rows).to_csv(truth / "lost_sales.csv.gz", index=False)
    sizes = pairs["size"].to_numpy()
    stats.update(
        skus=len(products), stores=n_stores, store_sku_pairs=P, policy=policy,
        stockout_rate=round(float(stockout_days.sum() / max(active_days.sum(), 1)), 4),
        fill_rate=round(stats["units"] / max(stats["demand_units"], 1), 4),
        avg_inventory_units=round(on_hand_sum / days, 1),
        stockout_rate_by_size={s: round(float(stockout_days[sizes == s].sum()
                                              / max(active_days[sizes == s].sum(), 1)), 4)
                               for s in pd.unique(sizes)},
    )
    return stats


# --------------------------------------------------------------------------- utilidades


def _inject_sales_issues(df: pd.DataFrame, rng: np.random.Generator, q: Quality) -> pd.DataFrame:
    n = len(df)
    df = df.astype({"unit_price": float, "store_id": object, "sku": object})
    neg = rng.random(n) < q.negative_price_rate
    df.loc[neg, "unit_price"] = -df.loc[neg, "unit_price"]
    df.loc[rng.random(n) < q.null_store_rate, "store_id"] = None
    low = rng.random(n) < q.lowercase_sku_rate
    df.loc[low, "sku"] = df.loc[low, "sku"].str.lower()
    return df


def _flush_returns(buffer: list[pd.DataFrame], ds: str, out: Path, stats: dict) -> None:
    if not buffer:
        return
    allr = pd.concat(buffer, ignore_index=True)
    today = allr[allr["returned_at"] == ds]
    buffer[:] = [allr[allr["returned_at"] > ds]]
    if len(today):
        r = today.reset_index(drop=True)
        out_df = pd.DataFrame({
            "return_id": [f"R-{t}" for t in r["transaction_id"]],
            "transaction_id": r["transaction_id"],
            "store_id": r["store_id"],
            "sku": r["sku"],
            "quantity": r["quantity"],
            "reason": r["reason"],
            "refund_amount": r["net_amount"],
            "currency": r["currency"],
            "returned_at": r["returned_at"],
        })
        _write_csv(out_df, out / "returns" / f"date={ds}" / "returns.csv")
        stats["returns"] += len(out_df)


def _write_inventory(pairs: pd.DataFrame, on_hand: np.ndarray, in_transit: np.ndarray, ds: str,
                     out: Path, rng: np.random.Generator, q: Quality, stats: dict) -> None:
    stores = pairs["store_id"].unique()
    missing = set(stores[rng.random(len(stores)) < q.missing_inventory_rate])
    keep = ~pairs["store_id"].isin(missing).to_numpy()
    oh = on_hand.astype(int).copy()
    oh[rng.random(len(oh)) < q.negative_on_hand_rate] *= -1
    path = out / "inventory" / f"date={ds}" / "inventory.jsonl.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    transit = in_transit.sum(axis=0).astype(int)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for s, sku, o, tr in zip(pairs["store_id"].to_numpy()[keep], pairs["sku"].to_numpy()[keep],
                                 oh[keep], transit[keep]):
            f.write(json.dumps({"snapshot_date": ds, "store_id": s, "sku": sku,
                                "on_hand": int(o), "in_transit": int(tr)}) + "\n")
    stats["inventory_rows"] += int(keep.sum())


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/raw"))
    p.add_argument("--truth", type=Path, default=Path("data/truth"))
    p.add_argument("--start", type=dt.date.fromisoformat, default=dt.date(2025, 1, 1))
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--stores", type=int, default=12)
    p.add_argument("--models", type=int, default=40)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--policy", choices=POLICIES, default="even_split",
                   help="Política de reposición del planner (default: práctica actual)")
    p.add_argument("--weather-dir", type=Path, default=None,
                   help="Carpeta con city=<x>/weather.json (ver ingest_external.py)")
    p.add_argument("--holidays-dir", type=Path, default=None,
                   help="Carpeta con country=<xx>/<year>.json (ver ingest_external.py)")
    a = p.parse_args()
    stats = simulate(a.out, a.truth, a.start, a.days, a.stores, a.models, a.seed,
                     a.weather_dir, a.holidays_dir, policy=a.policy)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
