"""Integration test against the real Postgres container (skipped if unreachable)."""
import os

import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.bronze import count_batch, load_bronze, new_batch_id
from pipeline.db import get_engine


@pytest.fixture(scope="module")
def engine():
    if not os.getenv("POSTGRES_HOST"):
        pytest.skip("POSTGRES_HOST not set")
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unreachable: {exc}")
    return eng


def test_load_bronze_persists_exact_row_count_and_raw_text(engine):
    raw = pd.read_csv("tests/fixtures/precios_sample.csv", dtype=str)
    batch = new_batch_id()
    loaded = load_bronze(raw, engine, batch_id=batch, source_url="fixture")
    assert loaded == 30
    assert count_batch(engine, batch) == 30
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT precio_medio, fecha_inicial FROM bronze.precios_raw "
                 "WHERE _batch_id = :b LIMIT 1"),
            {"b": batch},
        ).one()
    assert isinstance(row.precio_medio, str)
    assert "de" in row.fecha_inicial  # untouched Spanish text date
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM bronze.precios_raw WHERE _batch_id = :b"), {"b": batch})
