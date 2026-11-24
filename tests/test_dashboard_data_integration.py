"""Dashboard queries against the real Postgres test database."""
from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import text

from dashboard import data
from dashboard.whatif import price_risers
from pipeline.gold import build_gold
from pipeline.run import run_pipeline

SEED_ROWS = [
    ("Tomate", "Pereira", 100, date(2024, 1, 6)),
    ("Tomate", "Pereira", 200, date(2024, 1, 29)),
    ("Tomate", "Pereira", 180, date(2024, 2, 10)),   # +20 %
    ("Tomate", "Armenia", 400, date(2024, 1, 6)),
    ("Tomate", "Armenia", 300, date(2024, 2, 3)),    # -25 %
    ("Patilla", "Pereira", 50, date(2024, 1, 6)),
    ("Patilla", "Pereira", 50, date(2024, 2, 3)),    # 0 %
]


@pytest.fixture(autouse=True)
def clean_tables(engine):
    def wipe():
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE bronze.precios_raw, silver.precios, gold.precio_mensual, "
                "gold.variacion_mensual, meta.quality_runs"))
    wipe()
    yield
    wipe()


def _seed_silver(engine):
    with engine.begin() as conn:
        for producto, ciudad, medio, fecha in SEED_ROWS:
            conn.execute(
                text("INSERT INTO silver.precios (producto, mercado, categoria, ciudad, "
                     "precio_minimo, precio_maximo, precio_medio, fecha_inicial, fecha_final, "
                     "_batch_id) VALUES (:p, 'M', 'Frutas', :c, :m, :m, :m, :fi, :ff, 'seed')"),
                {"p": producto, "c": ciudad, "m": medio, "fi": fecha,
                 "ff": fecha + timedelta(days=5)})
    build_gold(engine)


def test_empty_database_has_no_approved_data(engine):
    assert data.has_approved_data(engine) is False
    assert data.last_approved_bronze(engine) is None
    assert data.quality_runs(engine).empty


def test_gold_queries_return_typed_ordered_frames(engine):
    _seed_silver(engine)
    assert data.has_approved_data(engine) is True

    options = data.products_and_cities(engine)
    assert {("Tomate", "Pereira"), ("Tomate", "Armenia"), ("Patilla", "Pereira")} == set(
        zip(options["producto"], options["ciudad"]))

    series = data.price_series(engine, "Tomate", "Pereira")
    assert series["mes"].tolist() == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")]
    assert series["precio_promedio"].tolist() == [150.0, 180.0]
    assert series["precio_promedio"].dtype.kind == "f"


def test_gold_risers_match_the_pandas_ranking_used_by_the_what_if(engine):
    """The SQL ranking (gold) and the pandas ranking (what-if) must agree."""
    _seed_silver(engine)
    from_gold = data.risers(engine, top_n=5)
    from_pandas = price_risers(data.all_monthly(engine), top_n=5)
    assert list(zip(from_gold["producto"], from_gold["ciudad"], from_gold["variacion_pct"])) == [
        ("Tomate", "Pereira", 20.0), ("Patilla", "Pereira", 0.0), ("Tomate", "Armenia", -25.0)]
    pd.testing.assert_frame_equal(
        from_gold.reset_index(drop=True), from_pandas.reset_index(drop=True), check_dtype=False)


def test_quality_runs_summarize_failed_rules(engine):
    run_pipeline(engine, source="fixture")
    run_pipeline(engine, source="fixture", corrupt=["duplicates"])
    runs = data.quality_runs(engine)
    assert runs["passed"].tolist() == [False, True]  # most recent first
    assert runs.loc[0, "failed_rules"] == "key_unique"
    assert runs.loc[1, "failed_rules"] == ""
    assert {"batch_id", "rows_checked", "executed_at"} <= set(runs.columns)


def test_last_approved_bronze_is_the_batch_silver_holds_not_the_rejected_one(engine):
    good = run_pipeline(engine, source="fixture")
    run_pipeline(engine, source="fixture", corrupt=["duplicates"])  # rejected, 31 rows in bronze
    bronze = data.last_approved_bronze(engine)
    assert len(bronze) == 30
    assert good.bronze_rows == 30
    assert "productos" in bronze.columns
