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
    assert any("Todavía no hay datos aprobados" in i.value for i in at.info)


def test_app_renders_every_section_in_spanish_with_approved_data(engine):
    run_pipeline(engine, source="fixture")
    at = _run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    assert any("Control de calidad" in h for h in headers)
    assert any("Precios" in h for h in headers)
    assert any("sin el control" in h.lower() for h in headers)
    assert at.selectbox(key="product").label == "Producto"
    assert at.selectbox(key="city").label == "Ciudad"
    assert len(at.get("plotly_chart")) >= 1


def test_corruption_kinds_are_offered_with_spanish_names(engine):
    run_pipeline(engine, source="fixture")
    options = _run().multiselect(key="whatif_kinds").options
    assert "Filas duplicadas" in options and "Precios nulos" in options
    assert "duplicates" not in options  # the code identifier is not shown to the reader


def test_what_if_with_duplicates_shows_the_gate_rejecting_the_batch(engine):
    run_pipeline(engine, source="fixture")
    at = _run()
    at.multiselect(key="whatif_kinds").set_value(["duplicates"]).run()
    assert not at.exception
    assert any("RECHAZADO" in e.value for e in at.error)


def test_what_if_admits_when_the_gate_misses_the_corruption(engine):
    """unit_error is invisible to the gate on the small sample: the app must say so."""
    run_pipeline(engine, source="fixture")
    at = _run()
    at.multiselect(key="whatif_kinds").set_value(["unit_error"]).run()
    assert not at.exception
    assert any("NO detectó" in w.value for w in at.warning)
