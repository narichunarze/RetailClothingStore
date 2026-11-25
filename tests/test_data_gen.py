import datetime as dt
import gzip
import json

import pandas as pd
import pytest

from src.data_gen import calendar_effects as ce
from src.data_gen.generate import simulate


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("gen")
    stats = simulate(root / "raw", root / "truth", dt.date(2025, 11, 1), 45,
                     n_stores=4, n_models=10, seed=7)
    return root, stats


def _sales(root):
    return pd.concat(pd.read_csv(f) for f in (root / "raw" / "sales").glob("*/sales.csv"))


def test_outputs_exist(generated):
    root, stats = generated
    raw = root / "raw"
    assert (raw / "master" / "products.csv").exists()
    assert (raw / "master" / "stores.csv").exists()
    assert len(list((raw / "inventory").glob("date=*/inventory.jsonl.gz"))) == 45
    assert stats["sales_lines"] > 0 and stats["returns"] > 0


def test_quality_issues_are_injected(generated):
    root, _ = generated
    s = _sales(root)
    assert s["transaction_id"].duplicated().any()
    assert (s["unit_price"] < 0).any()
    assert s["store_id"].isna().any()


def test_closed_on_christmas(generated):
    root, _ = generated
    assert not (root / "raw" / "sales" / "date=2025-12-25").exists()


def test_inventory_schema(generated):
    root, _ = generated
    f = next((root / "raw" / "inventory").glob("date=*/inventory.jsonl.gz"))
    with gzip.open(f, "rt") as fh:
        row = json.loads(fh.readline())
    assert set(row) == {"snapshot_date", "store_id", "sku", "on_hand", "in_transit"}


def test_deterministic_with_seed(tmp_path):
    a = simulate(tmp_path / "a", None, dt.date(2025, 1, 1), 10, 2, 4, seed=1)
    b = simulate(tmp_path / "b", None, dt.date(2025, 1, 1), 10, 2, 4, seed=1)
    assert a == b


def test_black_friday_and_seasons():
    assert ce.nth_weekday(2025, 11, 4, 4) == dt.date(2025, 11, 28)
    jan = dt.date(2025, 1, 15)
    # enero: verano en el sur, invierno en el norte
    assert ce.season_factor("summer", jan, "S") > ce.season_factor("summer", jan, "N")
    assert ce.season_factor("all", jan, "S") == 1.0


def test_policies_face_identical_demand_and_size_aware_wins():
    args = (None, None, dt.date(2025, 3, 1), 90, 3, 8, 5)
    even = simulate(*args, policy="even_split")
    aware = simulate(*args, policy="size_aware")
    assert even["demand_units"] == aware["demand_units"]  # contrafactual justo
    assert aware["lost_units"] < even["lost_units"]
    assert aware["stockout_rate_by_size"]["M"] < even["stockout_rate_by_size"]["M"]


def test_no_files_written_without_out(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    simulate(None, None, dt.date(2025, 1, 1), 5, 2, 3, 1)
    assert not any(tmp_path.rglob("*"))


def test_unknown_policy_rejected():
    with pytest.raises(ValueError):
        simulate(None, None, dt.date(2025, 1, 1), 5, 2, 3, 1, policy="magic")


def test_site_data_export_structure():
    from src.data_gen.export_site_data import build

    d = build(start=dt.date(2025, 3, 1), days=60, summary_seeds=[1], n_stores=3, n_models=8)
    assert set(d["policies"]) == {"even_split", "size_curve", "size_aware"}
    assert [r["size"] for r in d["size_curve"]] == ["XS", "S", "M", "L", "XL", "XXL"]
    assert abs(sum(r["demand_share"] for r in d["size_curve"]) - 1) < 0.01
    assert len(d["policies"]["even_split"]["weekly"]) >= 8
    assert d["summary"]["even_split"]["lost_units_vs_current"] == 0
