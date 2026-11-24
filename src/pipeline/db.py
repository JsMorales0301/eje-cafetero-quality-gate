"""Database connection built from environment variables (never hardcoded)."""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL


def get_engine(database: Optional[str] = None, **engine_kwargs) -> Engine:
    """Engine for POSTGRES_DB, or for `database` when given (used by isolated tests)."""
    url = URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=database or os.environ["POSTGRES_DB"],
    )
    return create_engine(url, pool_pre_ping=True, **engine_kwargs)
