"""End-to-end orchestrator runs against the real Postgres test database."""
import pytest
from sqlalchemy import text

from pipeline.run import EXIT_GATE_FAILED, EXIT_OK, EXIT_ERROR, parse_args, run_pipeline


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


def _count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def _silver_batches(engine):
    with engine.connect() as conn:
        return {r[0] for r in conn.execute(text("SELECT DISTINCT _batch_id FROM silver.precios"))}


def test_clean_fixture_run_populates_every_layer(engine):
    result = run_pipeline(engine, source="fixture")
    assert result.exit_code == EXIT_OK
    assert result.failed_stage is None
    assert result.bronze_rows == 30 and result.silver_rows == 30
    assert result.gold_rows > 0
    assert _count(engine, "gold.precio_mensual") == result.gold_rows
    assert _silver_batches(engine) == {result.batch_id}


def test_corrupted_run_stops_at_the_quality_gate_and_keeps_last_good_data(engine):
    good = run_pipeline(engine, source="fixture")
    gold_before = _count(engine, "gold.precio_mensual")

    bad = run_pipeline(engine, source="fixture", corrupt=["duplicates", "nulls"])

    assert bad.exit_code == EXIT_GATE_FAILED
    assert bad.failed_stage == "quality_gate"
    assert bad.gate_report is not None and bad.gate_report.passed is False
    assert bad.silver_rows is None and bad.gold_rows is None  # never reached
    assert _silver_batches(engine) == {good.batch_id}
    assert _count(engine, "gold.precio_mensual") == gold_before
    assert _count(engine, "bronze.precios_raw") > 30  # raw history keeps the rejected batch
    with engine.connect() as conn:
        passed = [r[0] for r in conn.execute(
            text("SELECT passed FROM meta.quality_runs ORDER BY id"))]
    assert passed == [True, False]


def test_unknown_corruption_kind_is_an_error_not_a_gate_failure(engine):
    result = run_pipeline(engine, source="fixture", corrupt=["gremlins"])
    assert result.exit_code == EXIT_ERROR
    assert result.failed_stage == "corrupt"
    assert _count(engine, "bronze.precios_raw") == 0  # nothing was loaded


def test_parse_args_defaults_and_corruption_list():
    args = parse_args([])
    assert args.source == "live" and args.corrupt == []
    args = parse_args(["--source", "fixture", "--corrupt", "nulls,duplicates"])
    assert args.source == "fixture" and args.corrupt == ["nulls", "duplicates"]


def test_parse_args_rejects_unknown_source():
    with pytest.raises(SystemExit):
        parse_args(["--source", "ftp"])
