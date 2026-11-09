"""DB-backed API test fixtures.

Each test runs on one connection inside an outer transaction that is rolled back at the end.
The data tables are emptied *inside* that transaction and re-seeded with small synthetic data,
so tests are deterministic even against a database that already holds real data.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, delete, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from bachatcheck.config import Settings, get_settings
from bachatcheck.db import get_session
from bachatcheck.main import create_app
from bachatcheck.models import (
    FundSnapshot,
    FxRate,
    Instrument,
    JobRun,
    MacroObservation,
    MacroSeries,
    PriceBar,
    RawSnapshot,
    TaxRule,
)
from bachatcheck.returns.series import month_ends

TEST_END = date(2026, 11, 10)


@pytest.fixture
def db_conn() -> Iterator[Connection]:
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
    yield conn
    outer.rollback()
    conn.close()
    engine.dispose()


def _session(conn: Connection) -> Session:
    return Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)


def seed(s: Session) -> None:
    for model in (
        PriceBar,
        FundSnapshot,
        Instrument,
        MacroObservation,
        MacroSeries,
        FxRate,
        RawSnapshot,
        JobRun,
        TaxRule,
    ):
        s.execute(delete(model))

    def series(code: str, unit: str = "Percent") -> MacroSeries:
        m = MacroSeries(
            code=code,
            name=code,
            unit=unit,
            frequency="monthly",
            source="test",
            source_key=f"T.{code}",
        )
        s.add(m)
        s.flush()
        return m

    cpi = series("CPI_MOM")
    first = date(2024, 10, 31)
    for d in [first, *month_ends(first, date(2026, 11, 1))]:
        s.add(MacroObservation(series_id=cpi.id, date=d, value=D(1), source="test"))
    dep = series("DEPOSIT_RATE_FRESH")
    s.add(
        MacroObservation(series_id=dep.id, date=date(2020, 1, 31), value=D("4.29"), source="test")
    )
    tb = series("TBILL_3M")
    s.add(MacroObservation(series_id=tb.id, date=date(2024, 1, 1), value=D(12), source="test"))

    kse = Instrument(kind="index", symbol="KSE100", name="KSE-100 Index", source="test", extra={})
    ogdc = Instrument(kind="stock", symbol="OGDC", name="OGDC", source="test", extra={})
    mm = Instrument(
        kind="mutual_fund", symbol="test-cash-fund", name="Test Cash Fund", category="Money Market",
        is_shariah=False, return_basis="annualized", source="test", extra={},
    )  # fmt: skip
    s.add_all([kse, ogdc, mm])
    s.flush()
    # KSE100: 100 a year before TEST_END, 130 at the end. OGDC: 200 -> 220.
    for inst, p0, p1 in ((kse, D(100), D(130)), (ogdc, D(200), D(220))):
        s.add(PriceBar(instrument_id=inst.id, date=date(2025, 11, 7), close=p0, source="test"))
        s.add(
            PriceBar(
                instrument_id=inst.id, date=date(2026, 5, 7), close=(p0 + p1) / 2, source="test"
            )
        )
        s.add(PriceBar(instrument_id=inst.id, date=date(2026, 11, 6), close=p1, source="test"))
    for days_ago, nav in ((1, D("10.6639")), (2, D("10.6610"))):
        s.add(
            FundSnapshot(
                instrument_id=mm.id, as_of_date=TEST_END - timedelta(days=days_ago), nav=nav,
                ret_365d=D("10.72"), ret_ytd=D("10.83"), source="test",
            )
        )  # fmt: skip
    s.add(FxRate(base="USD", quote="PKR", date=date(2025, 11, 7), rate=D(280), provider="test"))
    s.add(FxRate(base="USD", quote="PKR", date=date(2026, 10, 30), rate=D(277), provider="test"))
    s.add(
        TaxRule(
            asset_class="stock", tax_type="capital_gains", filer_status="filer", rate=D("0.15"),
            effective_from=date(2025, 7, 1), verified=True, source_url="https://example.test/fbr",
        )
    )  # fmt: skip
    s.add(JobRun(source="sbp", status="success", rows_upserted=3, params={}))
    s.commit()


@pytest.fixture
def make_client(db_conn: Connection) -> Callable[..., TestClient]:
    with _session(db_conn) as s:
        seed(s)

    def factory(**overrides: object) -> TestClient:
        settings = Settings(cache_ttl_seconds=0, rate_limit_per_minute=10_000, **overrides)  # type: ignore[arg-type]
        app = create_app(settings)

        def session_override() -> Iterator[Session]:
            with _session(db_conn) as s:
                yield s

        app.dependency_overrides[get_session] = session_override
        app.dependency_overrides[get_settings] = lambda: settings
        return TestClient(app)

    return factory


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
