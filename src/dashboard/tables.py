"""Display tables. Narrow on purpose: two of them sit side by side.
Numbers follow the Spanish convention: decimal comma, thousands dot."""
from __future__ import annotations

import pandas as pd


def _spanish(number: str) -> str:
    """'20,157.5' -> '20.157,5': swap the separators without them colliding."""
    return number.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_cop(value: float) -> str:
    return _spanish(f"{value:,.0f}")


def format_pct(value: float) -> str:
    return _spanish(f"{value:+,.1f}") + " %"


def risers_table(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "producto": df["producto"],
        "ciudad": df["ciudad"],
        "actual (COP)": df["precio_promedio"].map(format_cop),
        "cambio": df["variacion_pct"].map(format_pct),
    }).reset_index(drop=True)
