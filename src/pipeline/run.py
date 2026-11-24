"""Pipeline orchestrator: extract -> bronze -> quality gate -> silver -> gold.

    python -m pipeline.run [--source live|fixture] [--corrupt KIND[,KIND...]] [--seed N]

Exit codes (so CI can tell what happened):
    0  every stage succeeded
    1  the quality gate rejected the batch (silver and gold keep the last approved data)
    2  any other failure; the failed stage is printed
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd
from sqlalchemy import Engine

from pipeline.corruption import KINDS
from pipeline.corruption import corrupt as inject_corruption
from pipeline.db import get_engine
from pipeline.gold import build_gold
from pipeline.ingest import DEFAULT_ROW_LIMIT, extract_live, load_batch, row_limit_from_env
from pipeline.promote import promote_batch
from pipeline.quality import QualityReport

EXIT_OK, EXIT_GATE_FAILED, EXIT_ERROR = 0, 1, 2
SAMPLE_PATH = Path(__file__).resolve().parents[2] / "data" / "sample" / "precios_sample.csv"


@dataclass
class RunResult:
    exit_code: int
    failed_stage: Optional[str] = None
    batch_id: Optional[str] = None
    bronze_rows: Optional[int] = None
    silver_rows: Optional[int] = None
    gold_rows: Optional[int] = None
    gate_report: Optional[QualityReport] = None
    message: str = ""


def _extract(source: str, url: Optional[str], limit: Optional[int]) -> tuple[pd.DataFrame, str]:
    if source == "fixture":
        return pd.read_csv(SAMPLE_PATH, dtype=str), f"fixture:{SAMPLE_PATH.name}"
    url = url or os.environ["SOCRATA_DATASET_URL"]
    return extract_live(url, limit), url


def run_pipeline(
    engine: Engine,
    source: str = "live",
    corrupt: Sequence[str] = (),
    seed: int = 42,
    limit: Optional[int] = DEFAULT_ROW_LIMIT,
    url: Optional[str] = None,
    log: Callable[[str], None] = print,
) -> RunResult:
    stage = "extract"
    result = RunResult(exit_code=EXIT_ERROR)
    try:
        df, source_url = _extract(source, url, limit)
        log(f"STAGE extract     OK     source={source} rows={len(df)}")

        if corrupt:
            stage = "corrupt"
            df = inject_corruption(df, corrupt, seed=seed)
            log(f"STAGE corrupt     OK     kinds={','.join(corrupt)} seed={seed} rows={len(df)}")

        stage = "bronze"
        result.batch_id, result.bronze_rows = load_batch(engine, df, source_url)
        log(f"STAGE bronze      OK     batch={result.batch_id} rows={result.bronze_rows}")

        stage = "quality_gate"
        report = promote_batch(engine, result.batch_id)
        result.gate_report = report
        if not report.passed:
            log(f"STAGE quality_gate FAILED failed={report.expectations_failed}/"
                f"{report.expectations_run} expectations; silver and gold keep the last "
                "approved data")
            for d in report.failed_details:
                log(f"  - {d['rule']} unexpected={d['unexpected_count']} "
                    f"observed={d['observed_value']}")
            result.exit_code, result.failed_stage = EXIT_GATE_FAILED, "quality_gate"
            result.message = "quality gate rejected the batch"
            return result
        result.silver_rows = report.rows_checked
        log(f"STAGE quality_gate OK     expectations={report.expectations_run} "
            f"silver_rows={result.silver_rows}")

        stage = "gold"
        result.gold_rows = build_gold(engine)["precio_mensual"]
        log(f"STAGE gold        OK     precio_mensual={result.gold_rows}")
    except Exception as exc:  # noqa: BLE001 - report the stage, never a bare traceback
        result.exit_code, result.failed_stage = EXIT_ERROR, stage
        result.message = f"{type(exc).__name__}: {exc}"
        log(f"STAGE {stage} FAILED {result.message}")
        return result

    result.exit_code = EXIT_OK
    return result


def _kinds(value: str) -> list[str]:
    return [k.strip() for k in value.split(",") if k.strip()]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline.run", description=__doc__.split("\n")[0])
    parser.add_argument("--source", choices=["live", "fixture"], default="live",
                        help="live: datos.gov.co API; fixture: deterministic local sample")
    parser.add_argument("--corrupt", type=_kinds, default=[], metavar="KINDS",
                        help=f"comma-separated corruption kinds: {', '.join(sorted(KINDS))}")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    result = run_pipeline(get_engine(), source=args.source, corrupt=args.corrupt,
                          seed=args.seed, limit=row_limit_from_env())
    if result.exit_code == EXIT_OK:
        print(f"RESULT OK bronze={result.bronze_rows} silver={result.silver_rows} "
              f"gold={result.gold_rows}")
    else:
        print(f"RESULT FAILED stage={result.failed_stage} exit={result.exit_code}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
