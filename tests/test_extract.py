import pandas as pd
import pytest

from pipeline.extract import SOURCE_COLUMNS, fetch_rows, fetch_source_count

HEADER = ",".join(SOURCE_COLUMNS)


def _csv_page(n_rows: int, start: int = 0) -> str:
    rows = [
        ",".join(f'"{v}"' for v in [
            "p%d" % (start + i), "Pereira, Mercasa", "100", "200", "150",
            "lunes, 1 de enero de 2024", "viernes, 5 de enero de 2024",
            "Frutas", "Pereira",
        ])
        for i in range(n_rows)
    ]
    return "\n".join([HEADER] + rows) + "\n"


class FakeResponse:
    def __init__(self, text: str = "", payload=None):
        self.text = text
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    """Serves CSV pages from a list of total rows, honoring $limit/$offset."""

    def __init__(self, total_rows: int):
        self.total_rows = total_rows
        self.calls = []

    def get(self, url, params=None, timeout=None):
        params = params or {}
        self.calls.append((url, dict(params)))
        if "$select" in params:
            return FakeResponse(payload=[{"count": str(self.total_rows)}])
        limit, offset = int(params["$limit"]), int(params["$offset"])
        n = max(0, min(limit, self.total_rows - offset))
        return FakeResponse(text=_csv_page(n, start=offset))


def test_fetch_rows_paginates_until_exhausted():
    session = FakeSession(total_rows=25)
    df = fetch_rows("https://x/resource/abc.csv", limit=None, page_size=10, session=session)
    assert len(df) == 25
    assert list(df.columns) == SOURCE_COLUMNS


def test_fetch_rows_respects_limit():
    session = FakeSession(total_rows=100)
    df = fetch_rows("https://x/resource/abc.csv", limit=15, page_size=10, session=session)
    assert len(df) == 15


def test_fetch_rows_orders_by_id_for_stable_pages():
    session = FakeSession(total_rows=5)
    fetch_rows("https://x/resource/abc.csv", limit=5, page_size=10, session=session)
    assert session.calls[0][1]["$order"] == ":id"


def test_fetch_rows_keeps_everything_as_text():
    session = FakeSession(total_rows=3)
    df = fetch_rows("https://x/resource/abc.csv", limit=3, page_size=10, session=session)
    assert all(df[c].map(lambda v: isinstance(v, str)).all() for c in df.columns)
    assert df["precio_medio"].iloc[0] == "150"


def test_fetch_rows_rejects_unexpected_schema():
    class BadSession:
        def get(self, url, params=None, timeout=None):
            return FakeResponse(text="a,b\n1,2\n")

    with pytest.raises(ValueError, match="columns"):
        fetch_rows("https://x/resource/abc.csv", limit=5, page_size=10, session=BadSession())


def test_fetch_source_count_uses_json_endpoint():
    session = FakeSession(total_rows=83813)
    assert fetch_source_count("https://x/resource/abc.csv", session=session) == 83813
    assert session.calls[0][0] == "https://x/resource/abc.json"


def test_sample_fixture_matches_source_schema():
    df = pd.read_csv("data/sample/precios_sample.csv", dtype=str)
    assert list(df.columns) == SOURCE_COLUMNS
    assert len(df) == 30
