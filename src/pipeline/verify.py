"""Verification of the example operation: did the pipeline give the expected result?

    python -m pipeline.verify [--expected PATH]

It compares what is in the database after `pipeline.run --source fixture` with the values in
`data/sample/expected_fixture.json` and reports EVERY difference. CI uses its exit code to
decide whether a build passes:

    0  the result is exactly the expected one
    1  at least one difference (each one is printed)
    2  the check itself could not run (missing file, no database...)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import Engine, text

from pipeline.db import get_engine

EXIT_OK, EXIT_MISMATCH, EXIT_ERROR = 0, 1, 2
EXPECTED_PATH = Path(__file__).resolve().parents[2] / "data" / "sample" / "expected_fixture.json"

_LATEST_BRONZE_BATCH = (
    "SELECT count(*) FROM bronze.precios_raw WHERE _batch_id = "
    "(SELECT _batch_id FROM bronze.precios_raw GROUP BY _batch_id "
    " ORDER BY max(_ingested_at) DESC LIMIT 1)"
)


def load_expected(path: Optional[Path] = None) -> dict:
    return json.loads(Path(path or EXPECTED_PATH).read_text(encoding="utf-8"))


def collect_actual(engine: Engine, samples: Sequence[dict]) -> dict:
    """What the database holds right now, in the same shape as the expected file."""
    with engine.connect() as conn:
        count = lambda sql: conn.execute(text(sql)).scalar_one()  # noqa: E731
        rows = {
            "bronze_latest_batch": count(_LATEST_BRONZE_BATCH),
            "silver": count("SELECT count(*) FROM silver.precios"),
            "gold_monthly": count("SELECT count(*) FROM gold.precio_mensual"),
        }
        gate = conn.execute(
            text("SELECT passed FROM meta.quality_runs ORDER BY id DESC LIMIT 1")).scalar()
        found = []
        for s in samples:
            row = conn.execute(
                text("SELECT precio_promedio, observaciones FROM gold.precio_mensual "
                     "WHERE producto = :p AND ciudad = :c AND mes = :m"),
                {"p": s["producto"], "c": s["ciudad"], "m": date.fromisoformat(s["mes"])},
            ).first()
            found.append({"found": row is not None,
                          "precio_promedio": str(row.precio_promedio) if row else None,
                          "observaciones": row.observaciones if row else None})
    return {"rows": rows, "gate_passed": gate, "samples": found}


def _same_price(expected: str, actual: Optional[str]) -> bool:
    return actual is not None and Decimal(expected) == Decimal(actual)


def compare(expected: dict, actual: dict) -> list[str]:
    """Every difference between the expected and the actual result (empty = identical)."""
    problems: list[str] = []

    for layer, wanted in expected["rows"].items():
        got = actual["rows"][layer]
        if got != wanted:
            problems.append(f"{layer.replace('_latest_batch', '')} rows: expected {wanted}, got {got}")

    if expected.get("quality_gate_passed"):
        gate = actual["gate_passed"]
        if gate is None:
            problems.append("last quality gate run: none recorded")
        elif not gate:
            problems.append("last quality gate run: expected passed, got rejected")

    for wanted, got in zip(expected["samples"], actual["samples"]):
        label = f"gold {wanted['producto']} / {wanted['ciudad']} / {wanted['mes']}"
        if not got["found"]:
            problems.append(f"{label}: row not found")
            continue
        if not _same_price(wanted["precio_promedio"], got["precio_promedio"]):
            problems.append(f"{label}: precio_promedio expected {wanted['precio_promedio']}, "
                            f"got {got['precio_promedio']}")
        if got["observaciones"] != wanted["observaciones"]:
            problems.append(f"{label}: observaciones expected {wanted['observaciones']}, "
                            f"got {got['observaciones']}")
    return problems


def verify_operation(engine: Engine, expected: Optional[dict] = None) -> list[str]:
    expected = expected or load_expected()
    return compare(expected, collect_actual(engine, expected["samples"]))


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.verify", description=__doc__.split("\n")[0])
    parser.add_argument("--expected", type=Path, default=None,
                        help="expected-result file (default: data/sample/expected_fixture.json)")
    args = parser.parse_args(argv)
    try:
        expected = load_expected(args.expected)
        problems = verify_operation(get_engine(), expected)
    except Exception as exc:  # noqa: BLE001 - a broken check is not a failed result
        print(f"VERIFY ERROR {type(exc).__name__}: {exc}")
        return EXIT_ERROR

    if not problems:
        rows = expected["rows"]
        print(f"VERIFY OK bronze={rows['bronze_latest_batch']} silver={rows['silver']} "
              f"gold={rows['gold_monthly']} samples={len(expected['samples'])}")
        return EXIT_OK
    print(f"VERIFY FAILED {len(problems)} difference(s) from the expected result")
    for problem in problems:
        print(f"  - {problem}")
    return EXIT_MISMATCH


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
