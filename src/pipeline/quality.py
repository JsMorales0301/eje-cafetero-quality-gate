"""Quality gate: a Great Expectations suite that decides if a batch may enter silver.

Thresholds are calibrated against the full real dataset (83,813 rows, 2022-2025):
prices observed between 130 and 245,000 COP, max/min mean around 9,500 COP.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

# Keep the library quiet and private: no usage analytics, no progress bars.
os.environ.setdefault("GX_ANALYTICS_ENABLED", "false")
os.environ.setdefault("TQDM_DISABLE", "1")

import great_expectations as gx  # noqa: E402
import great_expectations.expectations as gxe  # noqa: E402
import pandas as pd  # noqa: E402
from great_expectations.data_context.types.base import ProgressBarsConfig  # noqa: E402

PRICE_COLUMNS = ["precio_minimo", "precio_maximo", "precio_medio"]
REQUIRED_COLUMNS = [
    "producto", "mercado", "categoria", "ciudad",
    *PRICE_COLUMNS, "fecha_inicial", "fecha_final",
]
CATEGORIES = [
    "Frutas", "Verduras y Hortalizas", "Carnes", "Procesados",
    "Tubérculos, Raíces y Plátanos", "Granos y Cereales", "Huevos y Lácteos", "Pescados",
]
CITIES = ["Pereira", "Ibagué", "Armenia", "Manizales"]
PRICE_MIN, PRICE_MAX = 1, 500_000
BATCH_MEAN_MIN, BATCH_MEAN_MAX = 1_000, 30_000
DATE_MIN = pd.Timestamp("2020-01-01")
FUTURE_TOLERANCE_DAYS = 60
UNIQUE_KEY = ["producto", "mercado", "fecha_inicial", "fecha_final"]


@dataclass
class QualityReport:
    passed: bool
    expectations_run: int
    expectations_failed: int
    rows_checked: int
    failed_details: list[dict] = field(default_factory=list)


def _rule(name: str) -> dict:
    return {"rule": name}


def build_suite(today: date) -> "gx.ExpectationSuite":
    date_max = pd.Timestamp(today) + timedelta(days=FUTURE_TOLERANCE_DAYS)
    suite = gx.ExpectationSuite(name="silver_gate")
    add = suite.add_expectation

    add(gxe.ExpectTableRowCountToBeBetween(min_value=1, meta=_rule("row_count_min")))

    for col in REQUIRED_COLUMNS:
        add(gxe.ExpectColumnValuesToNotBeNull(column=col, meta=_rule(f"not_null.{col}")))

    for col in PRICE_COLUMNS:
        add(gxe.ExpectColumnValuesToBeBetween(
            column=col, min_value=PRICE_MIN, max_value=PRICE_MAX,
            meta=_rule(f"price_plausible_range.{col}"),
        ))

    add(gxe.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="precio_maximo", column_B="precio_medio", or_equal=True,
        meta=_rule("price_order.maximo_gte_medio"),
    ))
    add(gxe.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="precio_medio", column_B="precio_minimo", or_equal=True,
        meta=_rule("price_order.medio_gte_minimo"),
    ))
    add(gxe.ExpectColumnPairValuesAToBeGreaterThanB(
        column_A="fecha_final", column_B="fecha_inicial", or_equal=True,
        meta=_rule("date_order.final_gte_inicial"),
    ))

    for col in ["fecha_inicial", "fecha_final"]:
        add(gxe.ExpectColumnValuesToBeBetween(
            column=col, min_value=DATE_MIN, max_value=date_max,
            meta=_rule(f"date_plausible_range.{col}"),
        ))

    add(gxe.ExpectColumnValuesToBeInSet(
        column="categoria", value_set=CATEGORIES, meta=_rule("category_in_set")))
    add(gxe.ExpectColumnValuesToBeInSet(
        column="ciudad", value_set=CITIES, meta=_rule("city_in_set")))
    add(gxe.ExpectCompoundColumnsToBeUnique(
        column_list=UNIQUE_KEY, meta=_rule("key_unique")))
    add(gxe.ExpectColumnMeanToBeBetween(
        column="precio_medio", min_value=BATCH_MEAN_MIN, max_value=BATCH_MEAN_MAX,
        meta=_rule("batch_mean.precio_medio")))
    return suite


def validate(df: pd.DataFrame, today: Optional[date] = None) -> QualityReport:
    """Run the suite on a silver candidate and summarize the outcome."""
    # The context must exist before the suite: adding expectations needs an active project.
    context = gx.get_context(mode="ephemeral")
    context.variables.progress_bars = ProgressBarsConfig(globally=False, metric_calculations=False)
    suite = build_suite(today or date.today())
    asset = context.data_sources.add_pandas("silver").add_dataframe_asset("candidate")
    batch = asset.add_batch_definition_whole_dataframe("whole").get_batch(
        batch_parameters={"dataframe": df}
    )
    result = batch.validate(suite)

    failed = []
    for r in result.results:
        if r.success:
            continue
        config = r.expectation_config
        info = r.exception_info or {}
        details = r.result or {}
        failed.append({
            "rule": (config.meta or {}).get("rule", config.type),
            "expectation": config.type,
            "unexpected_count": details.get("unexpected_count"),
            "observed_value": _plain(details.get("observed_value")),
            "error": info.get("exception_message") if info.get("raised_exception") else None,
        })

    stats = result.statistics
    return QualityReport(
        passed=bool(result.success),
        expectations_run=int(stats["evaluated_expectations"]),
        expectations_failed=int(stats["unsuccessful_expectations"]),
        rows_checked=int(len(df)),
        failed_details=failed,
    )


def _plain(value):
    """Make a GX observed value JSON-friendly."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)
