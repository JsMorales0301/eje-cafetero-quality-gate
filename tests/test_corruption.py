from datetime import date

import pandas as pd
import pytest

from pipeline.corruption import KINDS, corrupt
from pipeline.quality import validate
from pipeline.silver import build_silver_candidate

TODAY = date(2026, 11, 24)
PRICE_COLUMNS = ["precio_m_nimo", "precio_m_ximo", "precio_medio"]


def _clean() -> pd.DataFrame:
    return pd.read_csv("data/sample/precios_sample.csv", dtype=str)


def _gate(df: pd.DataFrame):
    report = validate(build_silver_candidate(df), today=TODAY)
    return report.passed, {d["rule"] for d in report.failed_details}


# Each kind below must be caught by the quality gate on the 30-row sample.
DETECTED_ON_SAMPLE = {
    "nulls": "not_null.precio_medio",
    "duplicates": "key_unique",
    "typo_zeros": "price_order.maximo_gte_medio",
    "negative": "price_plausible_range.precio_medio",
    "min_gt_max": "price_order.maximo_gte_medio",
    "bad_dates": "not_null.fecha_inicial",
    "bad_category": "category_in_set",
}


def test_registered_kinds():
    assert set(KINDS) == set(DETECTED_ON_SAMPLE) | {"unit_error"}


def test_clean_sample_passes_the_gate():
    assert _gate(_clean())[0] is True


@pytest.mark.parametrize("kind, expected_rule", sorted(DETECTED_ON_SAMPLE.items()))
def test_each_kind_is_rejected_by_the_gate(kind, expected_rule):
    passed, rules = _gate(corrupt(_clean(), [kind], seed=1))
    assert passed is False
    assert expected_rule in rules


def test_unit_error_multiplies_every_price_by_ten():
    clean = _clean()
    out = corrupt(clean, ["unit_error"], seed=1)
    for col in PRICE_COLUMNS:
        assert (pd.to_numeric(out[col]) == pd.to_numeric(clean[col]) * 10).all()


def test_combined_kinds_report_every_problem():
    passed, rules = _gate(corrupt(_clean(), ["nulls", "duplicates"], seed=1))
    assert passed is False
    assert {"not_null.precio_medio", "key_unique"} <= rules


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_each_kind_actually_changes_the_data(kind):
    clean = _clean()
    out = corrupt(clean, [kind], seed=1)
    assert not out.reset_index(drop=True).equals(clean)


def test_same_seed_gives_identical_corruption():
    a = corrupt(_clean(), ["nulls", "typo_zeros", "bad_dates"], seed=7)
    b = corrupt(_clean(), ["nulls", "typo_zeros", "bad_dates"], seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_input_is_not_mutated():
    clean = _clean()
    before = clean.copy()
    corrupt(clean, sorted(KINDS), seed=3)
    pd.testing.assert_frame_equal(clean, before)


def test_schema_stays_the_same_text_columns():
    out = corrupt(_clean(), ["duplicates", "nulls"], seed=1)
    assert list(out.columns) == list(_clean().columns)


def _with_prices(minimo: str, maximo: str, medio: str, n: int = 4) -> pd.DataFrame:
    df = _clean().head(n).copy()
    df["precio_m_nimo"], df["precio_m_ximo"], df["precio_medio"] = minimo, maximo, medio
    return df


def test_decimal_prices_keep_their_decimals_when_scaled():
    out = corrupt(_with_prices("2000.5", "2090.5", "2050.5"), ["unit_error"])
    assert set(out["precio_medio"]) == {"20505"}
    out = corrupt(_with_prices("1.25", "1.25", "12.25"), ["typo_zeros"], fraction=1.0)
    assert set(out["precio_medio"]) == {"1225"}


def test_negative_keeps_the_decimals_of_the_original_price():
    out = corrupt(_with_prices("2000.5", "2090.5", "2050.5"), ["negative"], fraction=1.0)
    assert set(out["precio_medio"]) == {"-2050.5"}


def test_min_gt_max_without_any_eligible_row_fails_loudly():
    with pytest.raises(ValueError, match="eligible"):
        corrupt(_with_prices("100", "100", "100"), ["min_gt_max"])


def test_min_gt_max_never_touches_rows_with_missing_prices():
    df = _with_prices("100", "200", "150", n=6)
    df.loc[0, "precio_m_nimo"] = None
    df.loc[1, "precio_m_ximo"] = None
    out = corrupt(df, ["min_gt_max"], fraction=1.0)
    assert pd.isna(out.loc[0, "precio_m_nimo"]) and out.loc[0, "precio_m_ximo"] == "200"
    assert out.loc[1, "precio_m_nimo"] == "100" and pd.isna(out.loc[1, "precio_m_ximo"])
    swapped = out.loc[2:, ["precio_m_nimo", "precio_m_ximo"]]
    assert (swapped["precio_m_nimo"] == "200").all() and (swapped["precio_m_ximo"] == "100").all()


def test_unknown_kind_is_rejected_with_the_valid_options():
    with pytest.raises(ValueError, match="unknown corruption") as err:
        corrupt(_clean(), ["gremlins"])
    assert "nulls" in str(err.value)
