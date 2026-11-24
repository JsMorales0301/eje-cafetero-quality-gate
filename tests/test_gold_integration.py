"""Gold aggregates against the real Postgres test database, with hand-computed values."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from pipeline.gold import build_gold

# (producto, categoria, ciudad, precio_medio, fecha_inicial)
SILVER_ROWS = [
    # Tomate / Pereira: January has 2 observations (100, 200) -> avg 150.
    # The second one starts on Jan 29 and ends in February: it belongs to January.
    ("Tomate", "Verduras y Hortalizas", "Pereira", 100, date(2024, 1, 6)),
    ("Tomate", "Verduras y Hortalizas", "Pereira", 200, date(2024, 1, 29)),
    # February: one observation of 180 -> +20.00% over January.
    ("Tomate", "Verduras y Hortalizas", "Pereira", 180, date(2024, 2, 10)),
    # March is missing, so April has no previous calendar month -> NULL variation.
    ("Tomate", "Verduras y Hortalizas", "Pereira", 300, date(2024, 4, 6)),
    # Same product in another city must be aggregated separately.
    ("Tomate", "Verduras y Hortalizas", "Armenia", 400, date(2024, 1, 6)),
    ("Tomate", "Verduras y Hortalizas", "Armenia", 300, date(2024, 2, 3)),  # -25.00%
    # A price that drops to zero variation.
    ("Patilla", "Frutas", "Pereira", 50, date(2024, 1, 6)),
    ("Patilla", "Frutas", "Pereira", 50, date(2024, 2, 3)),
]


@pytest.fixture()
def seeded(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE silver.precios"))
        for producto, categoria, ciudad, medio, fecha in SILVER_ROWS:
            conn.execute(
                text("INSERT INTO silver.precios (producto, mercado, categoria, ciudad, "
                     "precio_minimo, precio_maximo, precio_medio, fecha_inicial, fecha_final, "
                     "_batch_id) VALUES (:p, 'M', :c, :ci, :mn, :mx, :md, :fi, :ff, 'test')"),
                {"p": producto, "c": categoria, "ci": ciudad, "mn": medio - 10, "mx": medio + 10,
                 "md": medio, "fi": fecha, "ff": date(fecha.year, fecha.month, fecha.day)},
            )
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE silver.precios, gold.precio_mensual, gold.variacion_mensual"))


def _monthly(engine):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT producto, ciudad, mes, precio_promedio, observaciones "
            "FROM gold.precio_mensual"
        )).all()
    return {(r.producto, r.ciudad, r.mes): (r.precio_promedio, r.observaciones) for r in rows}


def _variation(engine):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT producto, ciudad, mes, precio_promedio, precio_anterior, variacion_pct "
            "FROM gold.variacion_mensual"
        )).all()
    return {(r.producto, r.ciudad, r.mes): (r.precio_anterior, r.variacion_pct) for r in rows}


def test_monthly_average_and_count_per_product_city_month(seeded):
    build_gold(seeded)
    monthly = _monthly(seeded)
    assert monthly[("Tomate", "Pereira", date(2024, 1, 1))] == (Decimal("150.00"), 2)
    assert monthly[("Tomate", "Pereira", date(2024, 2, 1))] == (Decimal("180.00"), 1)
    assert monthly[("Tomate", "Armenia", date(2024, 1, 1))] == (Decimal("400.00"), 1)
    assert len(monthly) == 7


def test_week_belongs_to_the_month_of_its_start_date(seeded):
    build_gold(seeded)
    monthly = _monthly(seeded)
    # The Jan 29 observation ends inside February in reality, but counts for January.
    assert monthly[("Tomate", "Pereira", date(2024, 1, 1))][1] == 2
    assert monthly[("Tomate", "Pereira", date(2024, 2, 1))][1] == 1


def test_variation_is_percent_change_against_previous_calendar_month(seeded):
    build_gold(seeded)
    var = _variation(seeded)
    assert var[("Tomate", "Pereira", date(2024, 2, 1))] == (Decimal("150.00"), Decimal("20.00"))
    assert var[("Tomate", "Armenia", date(2024, 2, 1))] == (Decimal("400.00"), Decimal("-25.00"))
    assert var[("Patilla", "Pereira", date(2024, 2, 1))] == (Decimal("50.00"), Decimal("0.00"))


def test_variation_is_null_without_a_previous_calendar_month(seeded):
    build_gold(seeded)
    var = _variation(seeded)
    assert var[("Tomate", "Pereira", date(2024, 1, 1))] == (None, None)  # first month
    assert var[("Tomate", "Pereira", date(2024, 4, 1))] == (None, None)  # March is missing


def test_rebuilding_gold_does_not_duplicate_rows(seeded):
    build_gold(seeded)
    first = (_monthly(seeded), _variation(seeded))
    build_gold(seeded)
    assert (_monthly(seeded), _variation(seeded)) == first


def test_gold_follows_silver_when_silver_changes(seeded):
    build_gold(seeded)
    with seeded.begin() as conn:
        conn.execute(text("DELETE FROM silver.precios WHERE ciudad = 'Armenia'"))
    build_gold(seeded)
    assert not any(k[1] == "Armenia" for k in _monthly(seeded))


def test_empty_silver_produces_empty_gold(seeded):
    with seeded.begin() as conn:
        conn.execute(text("TRUNCATE silver.precios"))
    build_gold(seeded)
    assert _monthly(seeded) == {} and _variation(seeded) == {}
