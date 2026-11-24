"""Gold layer: monthly aggregates built from silver, ready for decisions and the dashboard.

Gold is fully rebuilt from silver in one transaction, so it always reflects the last
approved batch and rebuilding never duplicates rows.

Conventions:
- A weekly observation belongs to the month of its start date (`fecha_inicial`).
- The variation is measured against the previous *calendar* month; it is NULL when that
  month has no data, so a gap is never silently compared against an older month.
"""
from __future__ import annotations

import sys

from sqlalchemy import Engine, text

from pipeline.db import get_engine

_MONTHLY_SQL = """
INSERT INTO gold.precio_mensual
    (producto, categoria, ciudad, mes, precio_promedio, observaciones)
SELECT producto,
       categoria,
       ciudad,
       date_trunc('month', fecha_inicial)::date AS mes,
       round(avg(precio_medio), 2),
       count(*)
FROM silver.precios
GROUP BY producto, categoria, ciudad, date_trunc('month', fecha_inicial)
"""

_VARIATION_SQL = """
INSERT INTO gold.variacion_mensual
    (producto, ciudad, mes, precio_promedio, precio_anterior, variacion_pct)
SELECT cur.producto,
       cur.ciudad,
       cur.mes,
       cur.precio_promedio,
       prev.precio_promedio,
       CASE WHEN prev.precio_promedio > 0
            THEN round((cur.precio_promedio - prev.precio_promedio)
                       / prev.precio_promedio * 100, 2)
       END
FROM gold.precio_mensual cur
LEFT JOIN gold.precio_mensual prev
       ON prev.producto = cur.producto
      AND prev.ciudad = cur.ciudad
      AND prev.mes = (cur.mes - INTERVAL '1 month')::date
"""


def build_gold(engine: Engine) -> dict[str, int]:
    """Rebuild both gold tables from silver. Returns the row count of each table."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE gold.precio_mensual, gold.variacion_mensual"))
        conn.execute(text(_MONTHLY_SQL))
        conn.execute(text(_VARIATION_SQL))
        monthly = conn.execute(text("SELECT count(*) FROM gold.precio_mensual")).scalar_one()
        variation = conn.execute(text("SELECT count(*) FROM gold.variacion_mensual")).scalar_one()
    return {"precio_mensual": monthly, "variacion_mensual": variation}


def main() -> int:
    counts = build_gold(get_engine())
    print(f"gold OK precio_mensual={counts['precio_mensual']} "
          f"variacion_mensual={counts['variacion_mensual']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
