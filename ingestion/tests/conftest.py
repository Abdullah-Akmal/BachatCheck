from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from bachatcheck.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_bytes() -> Callable[[str], bytes]:
    return lambda name: (FIXTURES / name).read_bytes()


@pytest.fixture
def session_factory() -> Iterator[Callable[[], Session]]:
    """Sessions on one connection inside an outer transaction that is rolled back afterwards.

    The runner's own commits become SAVEPOINT releases, so tests never leave data behind.
    Needs a migrated Postgres at DATABASE_URL; skipped otherwise.
    """
    engine = create_engine(get_settings().database_url)
    try:
        conn = engine.connect()
    except OperationalError as exc:
        pytest.skip(f"no Postgres available: {exc.__class__.__name__}")
    outer = conn.begin()
    try:
        conn.execute(text("SELECT 1 FROM job_runs LIMIT 1"))
    except ProgrammingError:
        outer.rollback()
        conn.close()
        pytest.skip("database is not migrated (run `alembic upgrade head`)")

    def factory() -> Session:
        return Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)

    yield factory
    outer.rollback()
    conn.close()
    engine.dispose()
