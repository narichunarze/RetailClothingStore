from src.quality import REQUIRED_NON_EMPTY, Metrics, evaluate


def _ok_counts():
    return {t: 100 for t in REQUIRED_NON_EMPTY}


def test_passes_with_healthy_metrics():
    assert evaluate(Metrics(_ok_counts(), sales_quarantine_rows=0, stockout_rate=0.05)) == []


def test_fails_on_empty_table():
    counts = _ok_counts() | {"gold_kpi_weekly": 0}
    assert any("gold_kpi_weekly" in f for f in evaluate(Metrics(counts, 0, 0.05)))


def test_fails_on_high_quarantine_share():
    counts = _ok_counts() | {"silver_sales": 950}
    failures = evaluate(Metrics(counts, sales_quarantine_rows=50, stockout_rate=0.05))
    assert any("cuarentena" in f for f in failures)


def test_fails_on_absurd_stockout_rate():
    assert evaluate(Metrics(_ok_counts(), 0, 0.9))
    assert evaluate(Metrics(_ok_counts(), 0, None))
