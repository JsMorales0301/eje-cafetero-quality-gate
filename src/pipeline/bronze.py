"""Bronze layer: raw data as received, plus lineage metadata. No cleaning here."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import Engine, text

from pipeline.extract import SOURCE_COLUMNS

# `_ingested_at` is filled by the database default.
METADATA_COLUMNS = ["_batch_id", "_source_url"]


def new_batch_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def prepare_bronze_frame(df: pd.DataFrame, batch_id: str, source_url: str) -> pd.DataFrame:
    missing = [c for c in SOURCE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Cannot load to bronze, missing columns: {missing}")
    out = df[SOURCE_COLUMNS].copy()
    out["_batch_id"] = batch_id
    out["_source_url"] = source_url
    return out


def load_bronze(df: pd.DataFrame, engine: Engine, batch_id: str, source_url: str) -> int:
    """Append the batch to bronze.precios_raw and return the number of rows written."""
    frame = prepare_bronze_frame(df, batch_id, source_url)
    frame.to_sql(
        "precios_raw",
        engine,
        schema="bronze",
        if_exists="append",
        index=False,
        method="multi",
        chunksize=1000,
    )
    return len(frame)


def count_batch(engine: Engine, batch_id: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM bronze.precios_raw WHERE _batch_id = :b"),
            {"b": batch_id},
        ).scalar_one()
