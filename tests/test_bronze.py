import pandas as pd
import pytest

from pipeline.bronze import METADATA_COLUMNS, new_batch_id, prepare_bronze_frame
from pipeline.extract import SOURCE_COLUMNS


def _sample() -> pd.DataFrame:
    return pd.read_csv("data/sample/precios_sample.csv", dtype=str)


def test_prepare_adds_metadata_without_touching_source_values():
    raw = _sample()
    out = prepare_bronze_frame(raw, batch_id="b1", source_url="https://x/abc.csv")
    assert list(out.columns) == SOURCE_COLUMNS + METADATA_COLUMNS
    assert (out["_batch_id"] == "b1").all()
    assert (out["_source_url"] == "https://x/abc.csv").all()
    pd.testing.assert_frame_equal(out[SOURCE_COLUMNS], raw[SOURCE_COLUMNS])


def test_prepare_does_not_mutate_input():
    raw = _sample()
    before = raw.copy()
    prepare_bronze_frame(raw, batch_id="b1", source_url="u")
    pd.testing.assert_frame_equal(raw, before)


def test_prepare_rejects_missing_columns():
    raw = _sample().drop(columns=["precio_medio"])
    with pytest.raises(ValueError, match="precio_medio"):
        prepare_bronze_frame(raw, batch_id="b1", source_url="u")


def test_batch_ids_are_unique():
    assert new_batch_id() != new_batch_id()
