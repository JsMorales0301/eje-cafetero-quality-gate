from datetime import date

import pandas as pd
import pytest

from pipeline.silver import SILVER_COLUMNS, build_silver_candidate, parse_spanish_date


@pytest.mark.parametrize(
    "text, expected",
    [
        ("sábado, 30 de marzo de 2024", date(2024, 3, 30)),
        ("viernes, 5 de abril de 2024", date(2024, 4, 5)),
        ("  viernes, 1 de enero de 2023 ", date(2023, 1, 1)),
        ("lunes, 12 de septiembre de 2022", date(2022, 9, 12)),
    ],
)
def test_parse_spanish_date_valid(text, expected):
    assert parse_spanish_date(text) == pd.Timestamp(expected)


@pytest.mark.parametrize(
    "text",
    ["", "garbage", "viernes, 31 de febrero de 2024", "viernes, 5 de abrilx de 2024", None],
)
def test_parse_spanish_date_invalid_is_nat(text):
    assert pd.isna(parse_spanish_date(text))


def _bronze_sample() -> pd.DataFrame:
    return pd.read_csv("data/sample/precios_sample.csv", dtype=str)


def test_candidate_has_typed_normalized_columns():
    out = build_silver_candidate(_bronze_sample())
    assert list(out.columns) == SILVER_COLUMNS
    assert len(out) == 30
    assert pd.api.types.is_numeric_dtype(out["precio_medio"])
    assert pd.api.types.is_datetime64_any_dtype(out["fecha_inicial"])
    assert out["fecha_inicial"].notna().all()


def test_candidate_keeps_bad_values_as_missing_instead_of_raising():
    raw = _bronze_sample()
    raw.loc[0, "precio_medio"] = "abc"
    raw.loc[1, "fecha_inicial"] = "not a date"
    out = build_silver_candidate(raw)
    assert pd.isna(out.loc[0, "precio_medio"])
    assert pd.isna(out.loc[1, "fecha_inicial"])
    assert len(out) == 30  # nothing is silently dropped


def test_candidate_strips_whitespace_and_does_not_deduplicate():
    raw = pd.concat([_bronze_sample(), _bronze_sample().head(1)], ignore_index=True)
    raw.loc[0, "productos"] = "  " + raw.loc[0, "productos"] + "  "
    out = build_silver_candidate(raw)
    assert out.loc[0, "producto"] == raw.loc[0, "productos"].strip()
    assert len(out) == 31  # duplicates are the quality gate's job to flag
