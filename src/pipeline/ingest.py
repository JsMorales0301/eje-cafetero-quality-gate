"""Extract + bronze load, verifying that bronze matches what was extracted."""
from __future__ import annotations

import os
import sys
from typing import Optional

import pandas as pd
from sqlalchemy import Engine

from pipeline.bronze import count_batch, load_bronze, new_batch_id
from pipeline.db import get_engine
from pipeline.extract import fetch_rows, fetch_source_count

DEFAULT_ROW_LIMIT = 5000


def extract_live(url: str, limit: Optional[int] = DEFAULT_ROW_LIMIT) -> pd.DataFrame:
    """Download a pinned window of the source, checking it against the source row count."""
    source_total = fetch_source_count(url)
    expected = source_total if limit is None else min(limit, source_total)
    df = fetch_rows(url, limit=limit)
    if len(df) != expected:
        raise RuntimeError(f"Extracted {len(df)} rows but expected {expected}")
    return df


def load_batch(engine: Engine, df: pd.DataFrame, source_url: str) -> tuple[str, int]:
    """Write a frame to bronze as a new batch and verify the stored row count."""
    batch_id = new_batch_id()
    load_bronze(df, engine, batch_id=batch_id, source_url=source_url)
    in_bronze = count_batch(engine, batch_id)
    if in_bronze != len(df):
        raise RuntimeError(f"Bronze has {in_bronze} rows for {batch_id}, expected {len(df)}")
    return batch_id, in_bronze


def run_ingest(url: str, limit: Optional[int] = DEFAULT_ROW_LIMIT) -> tuple[str, int]:
    """Load a pinned window of the source into bronze. Returns (batch_id, rows)."""
    return load_batch(get_engine(), extract_live(url, limit), url)


def row_limit_from_env() -> Optional[int]:
    raw = os.environ.get("SOCRATA_ROW_LIMIT", str(DEFAULT_ROW_LIMIT))
    return None if raw.lower() == "all" else int(raw)


def main() -> int:
    batch_id, rows = run_ingest(os.environ["SOCRATA_DATASET_URL"], row_limit_from_env())
    print(f"bronze OK batch={batch_id} rows={rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
