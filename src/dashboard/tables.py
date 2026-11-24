"""Display tables. Narrow on purpose: two of them sit side by side."""
from __future__ import annotations

import pandas as pd


def risers_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "product": df["producto"],
        "city": df["ciudad"],
        "current (COP)": df["precio_promedio"].map(lambda v: f"{v:,.0f}"),
        "change": df["variacion_pct"].map(lambda v: f"{v:+,.1f}%"),
    }).reset_index(drop=True)
