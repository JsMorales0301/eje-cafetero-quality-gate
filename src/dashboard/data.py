"""Read-only queries for the dashboard: gold layer plus the quality gate audit trail."""
from __future__ import annotations

from typing import Optional

import pandas as pd
from sqlalchemy import Engine, text

from pipeline.promote import read_bronze_batch


def _query(engine: Engine, sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def _typed(df: pd.DataFrame) -> pd.DataFrame:
    """Postgres NUMERIC arrives as Decimal and DATE as date: make them plain floats/timestamps."""
    for col in ("precio_promedio", "precio_anterior", "variacion_pct"):
        if col in df:
            df[col] = df[col].astype(float)
    if "mes" in df:
        df["mes"] = pd.to_datetime(df["mes"])
    return df


def has_approved_data(engine: Engine) -> bool:
    return bool(_query(engine, "SELECT EXISTS (SELECT 1 FROM gold.precio_mensual) AS ok")
                .loc[0, "ok"])


def products_and_cities(engine: Engine) -> pd.DataFrame:
    return _query(engine, "SELECT DISTINCT producto, ciudad FROM gold.precio_mensual "
                          "ORDER BY producto, ciudad")


def price_series(engine: Engine, producto: str, ciudad: str) -> pd.DataFrame:
    return _typed(_query(
        engine,
        "SELECT mes, precio_promedio, observaciones FROM gold.precio_mensual "
        "WHERE producto = :p AND ciudad = :c ORDER BY mes",
        p=producto, c=ciudad))


def all_monthly(engine: Engine) -> pd.DataFrame:
    return _typed(_query(
        engine,
        "SELECT producto, ciudad, mes, precio_promedio, observaciones "
        "FROM gold.precio_mensual ORDER BY producto, ciudad, mes"))


def risers(engine: Engine, top_n: int = 5) -> pd.DataFrame:
    """Biggest price increases in the latest month that has a variation (gold layer)."""
    return _typed(_query(
        engine,
        "SELECT producto, ciudad, mes, precio_anterior, precio_promedio, variacion_pct "
        "FROM gold.variacion_mensual "
        "WHERE variacion_pct IS NOT NULL AND mes = "
        "      (SELECT max(mes) FROM gold.variacion_mensual WHERE variacion_pct IS NOT NULL) "
        "ORDER BY variacion_pct DESC, producto, ciudad LIMIT :n",
        n=top_n))


def quality_runs(engine: Engine, limit: int = 10) -> pd.DataFrame:
    """Latest quality gate runs, most recent first, with the names of the failed rules."""
    return _query(
        engine,
        "SELECT executed_at, batch_id, passed, rows_checked, expectations_failed, "
        "       COALESCE((SELECT string_agg(d->>'rule', ', ') "
        "                 FROM jsonb_array_elements(failed_details) d), '') AS failed_rules "
        "FROM meta.quality_runs ORDER BY id DESC LIMIT :n",
        n=limit)


def last_approved_bronze(engine: Engine) -> Optional[pd.DataFrame]:
    """Raw rows of the batch silver currently holds (the last one the gate approved)."""
    batch = _query(engine, "SELECT _batch_id FROM silver.precios LIMIT 1")
    if batch.empty:
        return None
    return read_bronze_batch(engine, batch.loc[0, "_batch_id"]).astype(object)
