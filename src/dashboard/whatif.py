"""Pure functions for the dashboard: monthly prices, price risers and the "what if" scenario.

The "what if" answers one question: what would the dashboard show if a corrupted batch had
skipped the quality gate? It never touches the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

import pandas as pd

from pipeline.corruption import DEFAULT_FRACTION, corrupt
from pipeline.quality import QualityReport, validate
from pipeline.silver import build_silver_candidate

MONTHLY_COLUMNS = ["producto", "ciudad", "mes", "precio_promedio", "observaciones"]
RISER_COLUMNS = ["producto", "ciudad", "mes", "precio_anterior", "precio_promedio",
                 "variacion_pct"]


def monthly_prices(candidate: pd.DataFrame) -> pd.DataFrame:
    """Average price and observation count per product, city and month.

    Same convention as the gold layer: a weekly observation belongs to the month of its
    start date. Rows without a usable date or price cannot be grouped and are left out.
    """
    month = candidate["fecha_inicial"].dt.to_period("M").dt.to_timestamp()
    grouped = (
        candidate.assign(mes=month)
        .groupby(["producto", "ciudad", "mes"], as_index=False)
        .agg(precio_promedio=("precio_medio", "mean"), observaciones=("precio_medio", "size"))
    )
    grouped["precio_promedio"] = grouped["precio_promedio"].round(2)
    return grouped[MONTHLY_COLUMNS]


def price_risers(monthly: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Biggest percent increases against the previous calendar month.

    Uses the latest month that has at least one variation; a month whose previous month is
    missing has no variation (a gap is never compared against an older month).
    """
    previous = monthly[["producto", "ciudad", "mes", "precio_promedio"]].copy()
    previous["mes"] = previous["mes"] + pd.offsets.MonthBegin(1)
    previous = previous.rename(columns={"precio_promedio": "precio_anterior"})
    joined = monthly.merge(previous, on=["producto", "ciudad", "mes"], how="left")
    change = (joined["precio_promedio"] - joined["precio_anterior"]) / joined["precio_anterior"]
    joined["variacion_pct"] = (change * 100).where(joined["precio_anterior"] > 0).round(2)

    valid = joined.dropna(subset=["variacion_pct"])
    if valid.empty:
        return pd.DataFrame(columns=RISER_COLUMNS)
    latest = valid[valid["mes"] == valid["mes"].max()]
    ranked = latest.sort_values(["variacion_pct", "producto", "ciudad"],
                                ascending=[False, True, True])
    return ranked[RISER_COLUMNS].head(top_n).reset_index(drop=True)


@dataclass
class Simulation:
    candidate: pd.DataFrame   # typed silver candidate built from the corrupted batch
    report: QualityReport     # what the quality gate says about it
    monthly: pd.DataFrame     # what the dashboard would show if it had been let through


def simulate(
    bronze: pd.DataFrame,
    kinds: Sequence[str],
    seed: int = 42,
    fraction: float = DEFAULT_FRACTION,
    today: Optional[date] = None,
) -> Simulation:
    corrupted = corrupt(bronze, kinds, seed=seed, fraction=fraction)
    candidate = build_silver_candidate(corrupted)
    return Simulation(
        candidate=candidate,
        report=validate(candidate, today=today),
        monthly=monthly_prices(candidate),
    )
