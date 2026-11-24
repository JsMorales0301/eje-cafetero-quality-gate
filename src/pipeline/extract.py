"""Extraction from the datos.gov.co Socrata API.

Pages are requested ordered by `:id` so that a fixed row limit always returns the
same window of the dataset. Everything is read as text: typing belongs to silver.
"""
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import requests

SOURCE_COLUMNS = [
    "productos",
    "mercados",
    "precio_m_nimo",
    "precio_m_ximo",
    "precio_medio",
    "fecha_inicial",
    "fecha_final",
    "categoria",
    "ciudad",
]

DEFAULT_PAGE_SIZE = 5000
REQUEST_TIMEOUT_SECONDS = 60


def fetch_rows(
    url: str,
    limit: Optional[int] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    session=None,
) -> pd.DataFrame:
    """Download up to `limit` rows (all rows when None) as an all-text DataFrame."""
    session = session or requests
    pages: list[pd.DataFrame] = []
    offset = 0

    while limit is None or offset < limit:
        wanted = page_size if limit is None else min(page_size, limit - offset)
        response = session.get(
            url,
            params={"$limit": wanted, "$offset": offset, "$order": ":id"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        page = pd.read_csv(io.StringIO(response.text), dtype=str)

        missing = [c for c in SOURCE_COLUMNS if c not in page.columns]
        if missing:
            raise ValueError(f"Unexpected columns from source, missing: {missing}")

        pages.append(page[SOURCE_COLUMNS])
        offset += len(page)
        if len(page) < wanted:
            break

    if not pages:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    return pd.concat(pages, ignore_index=True)


def fetch_source_count(url: str, session=None) -> int:
    """Total number of rows the source currently holds."""
    session = session or requests
    json_url = url[:-4] + ".json" if url.endswith(".csv") else url
    response = session.get(
        json_url,
        params={"$select": "count(*)"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return int(response.json()[0]["count"])
