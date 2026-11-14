"""Database engine, session factory and declarative base."""

from collections.abc import Iterator
from functools import lru_cache

import structlog
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from bachatcheck.config import get_settings

# Deterministic constraint names, so Alembic migrations are stable across environments.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def optional_session() -> Iterator[Session | None]:
    """Like get_session, but yields None if the database can't even be configured.

    Used by the health check, which must answer "database unavailable" rather than crash when
    DATABASE_URL is missing or malformed.
    """
    try:
        factory = _session_factory()
    except SQLAlchemyError as exc:
        structlog.get_logger().error("db.misconfigured", error=type(exc).__name__)
        yield None
        return
    session = factory()
    try:
        yield session
    finally:
        session.close()
