"""The Streamlit app, executed headless against the real Postgres test database."""
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from pipeline.run import run_pipeline

APP = str(Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py")


@pytest.fixture(autouse=True)
def point_app_at_test_database(engine, monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", engine.url.database)
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE bronze.precios_raw, silver.precios, gold.precio_mensual, "
            "gold.variacion_mensual, meta.quality_runs"))
    yield
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE bronze.precios_raw, silver.precios, gold.precio_mensual, "
            "gold.variacion_mensual, meta.quality_runs"))


def _run() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def test_empty_database_explains_how_to_get_data(engine):
    at = _run()
    assert not at.exception
    assert any("No approved data" in i.value for i in at.info)


def test_app_renders_every_section_with_approved_data(engine):
    run_pipeline(engine, source="fixture")
    at = _run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    assert any("Quality gate" in h for h in headers)
    assert any("Prices" in h for h in headers)
    assert any("without the gate" in h.lower() for h in headers)
    assert at.selectbox(key="product") is not None and at.selectbox(key="city") is not None
    assert len(at.get("plotly_chart")) >= 1


def test_what_if_with_duplicates_shows_the_gate_rejecting_the_batch(engine):
    run_pipeline(engine, source="fixture")
    at = _run()
    at.multiselect(key="whatif_kinds").set_value(["duplicates"]).run()
    assert not at.exception
    assert any("REJECTED" in e.value for e in at.error)


def test_what_if_admits_when_the_gate_misses_the_corruption(engine):
    """unit_error is invisible to the gate on the small sample: the app must say so."""
    run_pipeline(engine, source="fixture")
    at = _run()
    at.multiselect(key="whatif_kinds").set_value(["unit_error"]).run()
    assert not at.exception
    assert any("did NOT detect" in w.value for w in at.warning)
