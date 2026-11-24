import os

import pytest
from sqlalchemy import text

from pipeline.db import get_engine


@pytest.fixture(scope="module")
def engine():
    """Real Postgres engine; the test is skipped when the database is unreachable."""
    if not os.getenv("POSTGRES_HOST"):
        pytest.skip("POSTGRES_HOST not set")
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unreachable: {exc}")
    return eng
