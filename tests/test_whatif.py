from datetime import date

import pandas as pd
import pytest

from dashboard.whatif import monthly_prices, price_risers, simulate
from pipeline.silver import SILVER_COLUMNS, build_silver_candidate

TODAY = date(2026, 11, 24)


def _candidate(rows) -> pd.DataFrame:
    """rows: (producto, ciudad, precio_medio, fecha_inicial)"""
    return pd.DataFrame(
        [
            (producto, "M", "Frutas", ciudad, medio, medio, medio,
             pd.Timestamp(fecha), pd.Timestamp(fecha) + pd.Timedelta(days=5))
            for producto, ciudad, medio, fecha in rows
        ],
        columns=SILVER_COLUMNS,
    )


ROWS = [
    ("Tomate", "Pereira", 100, "2024-01-06"),
    ("Tomate", "Pereira", 200, "2024-01-29"),   # week crosses into February, counts for January
    ("Tomate", "Pereira", 180, "2024-02-10"),   # +20.00 % over January
    ("Tomate", "Pereira", 300, "2024-04-06"),   # March is missing: no variation
    ("Tomate", "Armenia", 400, "2024-01-06"),
    ("Tomate", "Armenia", 300, "2024-02-03"),   # -25.00 %
    ("Patilla", "Pereira", 50, "2024-01-06"),
    ("Patilla", "Pereira", 50, "2024-02-03"),   # 0.00 %
]


def test_monthly_prices_average_and_count_per_product_city_month():
    monthly = monthly_prices(_candidate(ROWS)).set_index(["producto", "ciudad", "mes"])
    assert monthly.loc[("Tomate", "Pereira", pd.Timestamp("2024-01-01"))].tolist() == [150.0, 2]
    assert monthly.loc[("Tomate", "Pereira", pd.Timestamp("2024-02-01"))].tolist() == [180.0, 1]
    assert len(monthly) == 7


def test_monthly_prices_has_the_expected_columns_and_order():
    monthly = monthly_prices(_candidate(ROWS))
    assert list(monthly.columns) == ["producto", "ciudad", "mes", "precio_promedio", "observaciones"]


def test_price_risers_are_ranked_by_percent_change_in_the_latest_month_with_a_variation():
    risers = price_risers(monthly_prices(_candidate(ROWS)), top_n=5)
    assert risers["mes"].eq(pd.Timestamp("2024-02-01")).all()  # April has no previous month
    assert list(zip(risers["producto"], risers["ciudad"], risers["variacion_pct"])) == [
        ("Tomate", "Pereira", 20.0), ("Patilla", "Pereira", 0.0), ("Tomate", "Armenia", -25.0)]


def test_price_risers_respects_top_n():
    assert len(price_risers(monthly_prices(_candidate(ROWS)), top_n=1)) == 1


def test_price_risers_is_empty_when_no_month_has_a_previous_one():
    only_one_month = _candidate([("Tomate", "Pereira", 100, "2024-01-06")])
    risers = price_risers(monthly_prices(only_one_month))
    assert risers.empty
    assert list(risers.columns) == ["producto", "ciudad", "mes", "precio_anterior",
                                    "precio_promedio", "variacion_pct"]


def _bronze() -> pd.DataFrame:
    return pd.read_csv("data/sample/precios_sample.csv", dtype=str)


def test_simulate_without_corruption_matches_the_clean_pipeline():
    sim = simulate(_bronze(), [], today=TODAY)
    assert sim.report.passed is True
    pd.testing.assert_frame_equal(
        sim.monthly, monthly_prices(build_silver_candidate(_bronze())))


def test_simulate_reports_what_the_gate_would_do_with_a_corrupted_batch():
    sim = simulate(_bronze(), ["duplicates"], today=TODAY)
    assert sim.report.passed is False
    assert "key_unique" in {d["rule"] for d in sim.report.failed_details}
    assert len(sim.candidate) == 31


def test_simulate_shows_the_numbers_the_dashboard_would_have_shown_without_the_gate():
    clean = monthly_prices(build_silver_candidate(_bronze()))
    sim = simulate(_bronze(), ["unit_error"], today=TODAY)
    merged = clean.merge(sim.monthly, on=["producto", "ciudad", "mes"], suffixes=("_ok", "_bad"))
    assert (merged["precio_promedio_bad"] == merged["precio_promedio_ok"] * 10).all()


def test_simulate_does_not_mutate_the_input():
    bronze = _bronze()
    before = bronze.copy()
    simulate(bronze, ["nulls", "duplicates"], today=TODAY)
    pd.testing.assert_frame_equal(bronze, before)


def test_simulate_rejects_unknown_kinds():
    with pytest.raises(ValueError, match="unknown corruption"):
        simulate(_bronze(), ["gremlins"], today=TODAY)
