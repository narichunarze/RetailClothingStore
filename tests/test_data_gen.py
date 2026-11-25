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
