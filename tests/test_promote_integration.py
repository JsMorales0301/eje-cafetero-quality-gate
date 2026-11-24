"""Gate + silver promotion against the real Postgres container."""
import pandas as pd
from sqlalchemy import text

from pipeline.bronze import load_bronze, new_batch_id
from pipeline.promote import promote_batch


def _fixture() -> pd.DataFrame:
    return pd.read_csv("tests/fixtures/precios_sample.csv", dtype=str)


def _cleanup(engine, *batches):
    with engine.begin() as conn:
        for b in batches:
            conn.execute(text("DELETE FROM bronze.precios_raw WHERE _batch_id = :b"), {"b": b})
            conn.execute(text("DELETE FROM meta.quality_runs WHERE batch_id = :b"), {"b": b})
        conn.execute(text("TRUNCATE silver.precios"))


def _silver_batches(engine) -> set[str]:
    with engine.connect() as conn:
        return {r[0] for r in conn.execute(text("SELECT DISTINCT _batch_id FROM silver.precios"))}


def _runs(engine, batch):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT passed, failed_details FROM meta.quality_runs WHERE batch_id = :b"),
            {"b": batch},
        ).all()


def test_clean_batch_is_promoted_and_audited(engine):
    good = new_batch_id()
    load_bronze(_fixture(), engine, good, "fixture")
    try:
        report = promote_batch(engine, good)
        assert report.passed
        assert _silver_batches(engine) == {good}
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM silver.precios")).scalar_one() == 30
        runs = _runs(engine, good)
        assert len(runs) == 1 and runs[0].passed is True
    finally:
        _cleanup(engine, good)


def test_corrupted_batch_is_blocked_and_silver_keeps_last_good_data(engine):
    good, bad = new_batch_id(), new_batch_id()
    load_bronze(_fixture(), engine, good, "fixture")
    corrupted = _fixture()
    corrupted.loc[0, "precio_medio"] = "-1"
    corrupted = pd.concat([corrupted, corrupted.head(1)], ignore_index=True)  # duplicate key
    load_bronze(corrupted, engine, bad, "fixture-corrupted")
    try:
        assert promote_batch(engine, good).passed
        report = promote_batch(engine, bad)
        assert report.passed is False
        assert _silver_batches(engine) == {good}  # untouched by the rejected batch
        runs = _runs(engine, bad)
        assert len(runs) == 1 and runs[0].passed is False
        rules = {d["rule"] for d in runs[0].failed_details}
        assert "key_unique" in rules
    finally:
        _cleanup(engine, good, bad)


def test_promoting_the_same_batch_twice_does_not_duplicate_silver(engine):
    good = new_batch_id()
    load_bronze(_fixture(), engine, good, "fixture")
    try:
        promote_batch(engine, good)
        promote_batch(engine, good)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM silver.precios")).scalar_one() == 30
    finally:
        _cleanup(engine, good)
