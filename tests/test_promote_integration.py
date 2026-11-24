"""Gate + silver promotion against the real Postgres container."""
import pandas as pd
import pytest
from sqlalchemy import text

from pipeline.bronze import load_bronze, new_batch_id
from pipeline.promote import promote_batch, read_bronze_batch


def _fixture() -> pd.DataFrame:
    return pd.read_csv("data/sample/precios_sample.csv", dtype=str)


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


def test_load_failure_after_passing_gate_is_audited_and_keeps_silver(engine, monkeypatch):
    good, flaky = new_batch_id(), new_batch_id()
    load_bronze(_fixture(), engine, good, "fixture")
    load_bronze(_fixture(), engine, flaky, "fixture")
    try:
        assert promote_batch(engine, good).passed

        def boom(self, *args, **kwargs):
            raise RuntimeError("disk full")

        monkeypatch.setattr(pd.DataFrame, "to_sql", boom)
        with pytest.raises(RuntimeError, match="disk full"):
            promote_batch(engine, flaky)
        monkeypatch.undo()

        assert _silver_batches(engine) == {good}  # rollback kept the last good data
        runs = _runs(engine, flaky)
        assert len(runs) == 1 and runs[0].passed is False
        assert "silver_load_error" in {d["rule"] for d in runs[0].failed_details}
    finally:
        _cleanup(engine, good, flaky)


def test_reading_a_bronze_batch_does_not_depend_on_the_order_it_was_stored_in(engine):
    """A seeded corruption picks rows by position, so the same batch must always be read in
    the same order, or the dashboard's "what if" would show different numbers on each machine."""
    raw = _fixture()
    shuffled = raw.sample(frac=1, random_state=7).reset_index(drop=True)
    a, b = new_batch_id(), new_batch_id()
    load_bronze(raw, engine, a, "fixture")
    load_bronze(shuffled, engine, b, "fixture")
    try:
        pd.testing.assert_frame_equal(
            read_bronze_batch(engine, a).reset_index(drop=True),
            read_bronze_batch(engine, b).reset_index(drop=True))
    finally:
        _cleanup(engine, a, b)


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
