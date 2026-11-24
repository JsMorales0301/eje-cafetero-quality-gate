"""Controlled, reproducible data corruption, to show what a quality gate protects against.

Works on a bronze-shaped DataFrame (everything is text). The same seed always corrupts the
same rows, so a failing run can be reproduced exactly.
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

import numpy as np
import pandas as pd

PRICE_COLUMNS = ["precio_m_nimo", "precio_m_ximo", "precio_medio"]
DEFAULT_FRACTION = 0.02


def _pick(df: pd.DataFrame, rng: np.random.Generator, fraction: float,
          candidates: Optional[pd.Index] = None) -> pd.Index:
    """Choose at least one row (about `fraction` of the frame) among the candidates."""
    pool = df.index if candidates is None else candidates
    if len(pool) == 0:
        raise ValueError("no row is eligible for this corruption")
    n = min(len(pool), max(1, round(len(df) * fraction)))
    return pd.Index(rng.choice(pool, size=n, replace=False))


def _scaled(series: pd.Series, factor: float) -> pd.Series:
    """Multiply a text price column, keeping it as text and keeping missing values."""
    numeric = pd.to_numeric(series, errors="coerce") * factor
    return numeric.map(lambda v: None if pd.isna(v) else str(int(round(v))))


def nulls(df, rng, fraction):
    out = df.copy()
    out.loc[_pick(df, rng, fraction), "precio_medio"] = None
    return out


def duplicates(df, rng, fraction):
    copies = df.loc[_pick(df, rng, fraction)]
    return pd.concat([df, copies], ignore_index=True)


def unit_error(df, rng, fraction):
    """Every price multiplied by 10, as if the unit changed. Affects the whole batch."""
    out = df.copy()
    for col in PRICE_COLUMNS:
        out[col] = _scaled(df[col], 10)
    return out


def typo_zeros(df, rng, fraction):
    """A few average prices with two extra zeros."""
    out = df.copy()
    rows = _pick(df, rng, fraction)
    out.loc[rows, "precio_medio"] = _scaled(df.loc[rows, "precio_medio"], 100)
    return out


def negative(df, rng, fraction):
    out = df.copy()
    rows = _pick(df, rng, fraction)
    out.loc[rows, "precio_medio"] = _scaled(df.loc[rows, "precio_medio"], -1)
    return out


def min_gt_max(df, rng, fraction):
    """Swap minimum and maximum on rows where they differ."""
    out = df.copy()
    lo = pd.to_numeric(df["precio_m_nimo"], errors="coerce")
    hi = pd.to_numeric(df["precio_m_ximo"], errors="coerce")
    rows = _pick(df, rng, fraction, candidates=df.index[lo < hi])
    out.loc[rows, "precio_m_nimo"] = df.loc[rows, "precio_m_ximo"]
    out.loc[rows, "precio_m_ximo"] = df.loc[rows, "precio_m_nimo"]
    return out


def bad_dates(df, rng, fraction):
    out = df.copy()
    out.loc[_pick(df, rng, fraction), "fecha_inicial"] = "sin fecha"
    return out


def bad_category(df, rng, fraction):
    """Typo in the category (lower case plus a trailing space)."""
    out = df.copy()
    rows = _pick(df, rng, fraction)
    out.loc[rows, "categoria"] = df.loc[rows, "categoria"].str.lower() + " "
    return out


KINDS: dict[str, Callable] = {
    "nulls": nulls,
    "duplicates": duplicates,
    "unit_error": unit_error,
    "typo_zeros": typo_zeros,
    "negative": negative,
    "min_gt_max": min_gt_max,
    "bad_dates": bad_dates,
    "bad_category": bad_category,
}


def corrupt(df: pd.DataFrame, kinds: Iterable[str], seed: int = 42,
            fraction: float = DEFAULT_FRACTION) -> pd.DataFrame:
    """Return a corrupted copy of `df`; the input is never modified."""
    kinds = list(kinds)
    unknown = [k for k in kinds if k not in KINDS]
    if unknown:
        raise ValueError(f"unknown corruption kind(s): {unknown}. Valid: {sorted(KINDS)}")
    rng = np.random.default_rng(seed)
    out = df.reset_index(drop=True).copy()
    for kind in kinds:
        out = KINDS[kind](out, rng, fraction)
    return out
