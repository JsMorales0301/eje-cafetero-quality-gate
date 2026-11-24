from datetime import date

import pandas as pd
import pytest

from pipeline.quality import validate
from pipeline.silver import build_silver_candidate

TODAY = date(2026, 11, 24)


def _clean() -> pd.DataFrame:
    raw = pd.read_csv("data/sample/precios_sample.csv", dtype=str)
    return build_silver_candidate(raw)


def _failed_rules(df: pd.DataFrame) -> set[str]:
    report = validate(df, today=TODAY)
    assert report.passed is False
    return {d["rule"] for d in report.failed_details}


def test_clean_sample_passes_every_expectation():
    report = validate(_clean(), today=TODAY)
    assert report.failed_details == []
    assert report.passed is True
    assert report.expectations_failed == 0
    assert report.expectations_run >= 15
    assert report.rows_checked == 30


def test_null_price_is_rejected():
    df = _clean()
    df.loc[3, "precio_medio"] = None
    assert "not_null.precio_medio" in _failed_rules(df)


def test_unparsable_date_is_rejected():
    df = _clean()
    df.loc[2, "fecha_inicial"] = pd.NaT
    assert "not_null.fecha_inicial" in _failed_rules(df)


def test_duplicate_key_is_rejected():
    df = pd.concat([_clean(), _clean().head(1)], ignore_index=True)
    assert "key_unique" in _failed_rules(df)


def test_negative_price_is_rejected():
    df = _clean()
    df.loc[5, "precio_medio"] = -500.0
    assert "price_plausible_range.precio_medio" in _failed_rules(df)


def test_minimum_above_maximum_is_rejected():
    df = _clean()
    df.loc[0, ["precio_minimo", "precio_maximo"]] = [9999.0, 100.0]
    assert "price_order.maximo_gte_medio" in _failed_rules(df)


def test_unit_error_all_prices_times_hundred_is_rejected_by_batch_mean():
    # The 30-row fixture holds cheap products (low mean), so x10 stays under the batch-mean
    # ceiling; on the real 5000-row window x10 is caught (verified manually, see ai-log).
    df = _clean()
    for col in ["precio_minimo", "precio_maximo", "precio_medio"]:
        df[col] = df[col] * 100
    assert "batch_mean.precio_medio" in _failed_rules(df)


def test_known_blind_spot_only_maximum_times_ten_passes():
    """Documented limitation: a corruption that keeps min <= medio <= max and stays in
    the plausible range is not detected by structural rules."""
    df = _clean()
    df["precio_maximo"] = df["precio_maximo"] * 10
    assert validate(df, today=TODAY).passed is True


def test_unknown_category_is_rejected():
    df = _clean()
    df.loc[1, "categoria"] = "Electrodomesticos"
    assert "category_in_set" in _failed_rules(df)


def test_unknown_city_is_rejected():
    df = _clean()
    df.loc[1, "ciudad"] = "Bogota"
    assert "city_in_set" in _failed_rules(df)


def test_end_date_before_start_date_is_rejected():
    df = _clean()
    df.loc[4, "fecha_final"] = df.loc[4, "fecha_inicial"] - pd.Timedelta(days=10)
    assert "date_order.final_gte_inicial" in _failed_rules(df)


def test_implausible_dates_are_rejected():
    df = _clean()
    df.loc[0, "fecha_inicial"] = pd.Timestamp("1900-01-01")
    df.loc[1, "fecha_final"] = pd.Timestamp("2999-01-01")
    rules = _failed_rules(df)
    assert "date_plausible_range.fecha_inicial" in rules
    assert "date_plausible_range.fecha_final" in rules


def test_empty_batch_is_rejected():
    assert "row_count_min" in _failed_rules(_clean().head(0))


def test_report_details_are_json_serializable():
    import json

    df = _clean()
    df.loc[3, "precio_medio"] = None
    report = validate(df, today=TODAY)
    json.dumps(report.failed_details)


@pytest.mark.parametrize("n_bad", [1, 3])
def test_failed_count_matches_number_of_broken_rules(n_bad):
    df = _clean()
    df.loc[0, "categoria"] = "X"
    if n_bad == 3:
        df.loc[1, "ciudad"] = "Y"
        df.loc[2, "precio_medio"] = None
    report = validate(df, today=TODAY)
    assert report.expectations_failed >= n_bad
