import os
from pathlib import Path

import pytest
from sqlalchemy import text

from pipeline.db import get_engine

INIT_SQL = Path(__file__).resolve().parents[1] / "sql" / "init.sql"


@pytest.fixture(scope="session")
def engine():
    """Engine for a dedicated `<POSTGRES_DB>_test` database.

    Integration tests truncate tables, so they run on their own database, created on demand
    with the same schema as production. The real database is never touched.
    The test is skipped when the server is unreachable.
    """
    if not os.getenv("POSTGRES_HOST"):
        pytest.skip("POSTGRES_HOST not set")

    test_db = f"{os.environ['POSTGRES_DB']}_test"
    admin = get_engine(isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": test_db}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database unreachable: {exc}")
    finally:
        admin.dispose()

    eng = get_engine(database=test_db)
    with eng.begin() as conn:
        conn.exec_driver_sql(INIT_SQL.read_text())  # idempotent: CREATE ... IF NOT EXISTS
    yield eng
    eng.dispose()
