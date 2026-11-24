"""Promote a bronze batch to silver, only if it passes the quality gate.

Silver always reflects the last approved batch: a rejected batch leaves it untouched,
and every gate run (passed or failed) is recorded in meta.quality_runs.
"""
from __future__ import annotations

import json
import sys
from typing import Optional

import pandas as pd
from sqlalchemy import Engine, text

from pipeline.db import get_engine
from pipeline.extract import SOURCE_COLUMNS
from pipeline.quality import QualityReport, validate
from pipeline.silver import build_silver_candidate


def read_bronze_batch(engine: Engine, batch_id: str) -> pd.DataFrame:
    columns = ", ".join(SOURCE_COLUMNS)
    query = text(f"SELECT {columns} FROM bronze.precios_raw WHERE _batch_id = :b")
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"b": batch_id}).astype("string")


def latest_batch_id(engine: Engine) -> Optional[str]:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT _batch_id FROM bronze.precios_raw "
                 "GROUP BY _batch_id ORDER BY max(_ingested_at) DESC LIMIT 1")
        ).scalar()


def _record_run(conn, batch_id: str, report: QualityReport) -> None:
    conn.execute(
        text("INSERT INTO meta.quality_runs "
             "(batch_id, passed, expectations_run, expectations_failed, "
             " failed_details, rows_checked) "
             "VALUES (:b, :p, :run, :failed, CAST(:d AS JSONB), :rows)"),
        {
            "b": batch_id,
            "p": report.passed,
            "run": report.expectations_run,
            "failed": report.expectations_failed,
            "d": json.dumps(report.failed_details),
            "rows": report.rows_checked,
        },
    )


def promote_batch(engine: Engine, batch_id: str, today=None) -> QualityReport:
    candidate = build_silver_candidate(read_bronze_batch(engine, batch_id))
    report = validate(candidate, today=today)

    with engine.begin() as conn:
        if report.passed:
            conn.execute(text("TRUNCATE silver.precios"))
            candidate.assign(_batch_id=batch_id).to_sql(
                "precios", conn, schema="silver", if_exists="append",
                index=False, method="multi", chunksize=1000,
            )
        _record_run(conn, batch_id, report)
    return report


def main(argv: list[str]) -> int:
    engine = get_engine()
    batch_id = argv[1] if len(argv) > 1 else latest_batch_id(engine)
    if not batch_id:
        print("No bronze batch found. Run pipeline.ingest first.")
        return 2
    report = promote_batch(engine, batch_id)
    if report.passed:
        print(f"quality gate PASSED batch={batch_id} "
              f"rows={report.rows_checked} expectations={report.expectations_run}")
        return 0
    print(f"quality gate FAILED batch={batch_id} "
          f"failed={report.expectations_failed}/{report.expectations_run}")
    for d in report.failed_details:
        print(f"  - {d['rule']} unexpected={d['unexpected_count']} observed={d['observed_value']}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
