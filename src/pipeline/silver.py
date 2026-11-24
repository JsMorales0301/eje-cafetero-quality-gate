"""Silver candidate: typed and normalized data, built from a bronze batch.

Nothing is dropped or deduplicated here. Values that cannot be converted become
missing (NaN/NaT) so the quality gate can see and reject them, instead of the
transformation hiding the problem.
"""
from __future__ import annotations

import re

import pandas as pd

SILVER_COLUMNS = [
    "producto",
    "mercado",
    "categoria",
    "ciudad",
    "precio_minimo",
    "precio_maximo",
    "precio_medio",
    "fecha_inicial",
    "fecha_final",
]

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_DATE_RE = re.compile(r"^\s*[^\W\d_]+,\s*(\d{1,2}) de ([^\W\d_]+) de (\d{4})\s*$")


def parse_spanish_date(value) -> pd.Timestamp:
    """'sábado, 30 de marzo de 2024' -> Timestamp('2024-03-30'); invalid -> NaT."""
    if not isinstance(value, str):
        return pd.NaT
    match = _DATE_RE.match(value)
    if not match:
        return pd.NaT
    day, month_name, year = match.groups()
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return pd.NaT
    try:
        return pd.Timestamp(year=int(year), month=month, day=int(day))
    except ValueError:
        return pd.NaT


def build_silver_candidate(bronze: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "producto": bronze["productos"].str.strip(),
            "mercado": bronze["mercados"].str.strip(),
            "categoria": bronze["categoria"].str.strip(),
            "ciudad": bronze["ciudad"].str.strip(),
            "precio_minimo": pd.to_numeric(bronze["precio_m_nimo"], errors="coerce"),
            "precio_maximo": pd.to_numeric(bronze["precio_m_ximo"], errors="coerce"),
            "precio_medio": pd.to_numeric(bronze["precio_medio"], errors="coerce"),
            "fecha_inicial": pd.to_datetime(bronze["fecha_inicial"].map(parse_spanish_date)),
            "fecha_final": pd.to_datetime(bronze["fecha_final"].map(parse_spanish_date)),
        }
    )
    return out[SILVER_COLUMNS].reset_index(drop=True)
