"""Runner against a real Postgres: raw-first storage, idempotent upserts, job_runs bookkeeping."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bachatcheck.models import FxRate, JobRun, MacroObservation, PriceBar, RawSnapshot
from ingestion.providers.base import FetchContext, RawPayload
from ingestion.providers.frankfurter import FrankfurterProvider
from ingestion.providers.psx import PsxProvider
from ingestion.providers.sbp import SbpProvider
from ingestion.runner import run_job

pytestmark = pytest.mark.db
Factory = Callable[[], Session]
AS_OF = date(2026, 11, 10)


class FixtureSbp(SbpProvider):
    def __init__(self, content: bytes) -> None:
        self.content = content

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        return [RawPayload("sbp", "https://easydata.test/series/x/data", self.content, "json")]


class FixtureFx(FrankfurterProvider):
    def __init__(self, content: bytes) -> None:
        self.content = content

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        return [
            RawPayload("frankfurter", "https://frankfurter.test/v2/rates", self.content, "json")
        ]


def count(factory: Factory, model: type) -> int:
    with factory() as s:
        return s.execute(select(func.count()).select_from(model)).scalar_one()


def test_rerun_is_idempotent(
    session_factory: Factory, fixture_bytes: Callable[[str], bytes]
) -> None:
    provider = FixtureSbp(fixture_bytes("sbp_cpi_yoy.json"))
    before = count(session_factory, MacroObservation)

    first = run_job(provider, session_factory, FetchContext(as_of=AS_OF))
    after_first = count(session_factory, MacroObservation)
    second = run_job(provider, session_factory, FetchContext(as_of=AS_OF))
    after_second = count(session_factory, MacroObservation)

    assert (first.status, first.rows_upserted) == ("success", 4)
    assert (second.status, second.rows_upserted) == ("success", 4)
    # The DB may already hold these observations; either way a re-run adds nothing.
    assert before <= after_first <= before + 4
    assert after_second == after_first


def test_raw_payload_is_kept_when_parsing_fails(session_factory: Factory) -> None:
    before_raw = count(session_factory, RawSnapshot)
    result = run_job(
        FixtureFx(b"<html>not json</html>"), session_factory, FetchContext(as_of=AS_OF)
    )

    assert result.status == "failed"
    assert result.error and "parse" in result.error
    assert count(session_factory, RawSnapshot) == before_raw + 1
    with session_factory() as s:
        run = s.get_one(JobRun, result.job_run_id)
        assert run.status == "failed" and run.finished_at is not None


def test_failed_fetch_leaves_existing_data_alone(
    session_factory: Factory, fixture_bytes: Callable[[str], bytes]
) -> None:
    run_job(
        FixtureFx(fixture_bytes("frankfurter_usd_pkr.json")),
        session_factory,
        FetchContext(as_of=AS_OF),
    )
    rates_before = count(session_factory, FxRate)

    class Broken(FrankfurterProvider):
        def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
            raise ConnectionError("source down")

    result = run_job(Broken(), session_factory, FetchContext(as_of=AS_OF))
    assert result.status == "failed"
    assert "source down" in (result.error or "")
    assert count(session_factory, FxRate) == rates_before


def test_invalid_rows_are_skipped_and_counted(session_factory: Factory) -> None:
    csv_bytes = (
        b"date,open,high,low,close,volume,is_anomaly\n"
        b"2026-11-05,100,110,95,105,1000,False\n"
        b"2026-11-06,100,90,95,105,1000,True\n"  # high < low -> skipped
        b"2099-01-01,100,110,95,105,1000,False\n"  # future -> skipped
    )

    class FixturePsx(PsxProvider):
        def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
            return [RawPayload("psx", "psxdata://stocks/TESTSYM?start=a&end=b", csv_bytes, "csv")]

    before = count(session_factory, PriceBar)
    result = run_job(FixturePsx(), session_factory, FetchContext(as_of=AS_OF))
    assert (result.status, result.rows_upserted, result.rows_skipped) == ("success", 1, 2)
    assert count(session_factory, PriceBar) == before + 1


def test_partial_when_some_series_fail(
    session_factory: Factory, fixture_bytes: Callable[[str], bytes]
) -> None:
    class HalfBroken(FixtureSbp):
        def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
            ctx.errors.append("TBILL_3M: HTTP 503 (HTTPStatusError)")
            return super().fetch(ctx)

    result = run_job(
        HalfBroken(fixture_bytes("sbp_cpi_yoy.json")), session_factory, FetchContext(as_of=AS_OF)
    )
    assert result.status == "partial"
    assert result.rows_upserted == 4
