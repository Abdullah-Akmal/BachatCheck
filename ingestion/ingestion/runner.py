"""Runs one provider end to end and records the outcome in job_runs.

Order of operations per payload: save raw bytes (commit) -> parse -> validate -> upsert (commit).
A failed parse never loses the raw payload, and a failed source never touches existing data,
so the API keeps serving the last good values.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import update
from sqlalchemy.orm import Session

from bachatcheck.config import get_settings
from bachatcheck.models import JobRun, RawSnapshot
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import Record, today_pkt
from ingestion.writers import write_records

log = structlog.get_logger()


@dataclass
class JobResult:
    job_run_id: int
    status: str
    rows_upserted: int
    rows_skipped: int
    error: str | None


def redact(text: str) -> str:
    """Strip known secrets from anything we log or store."""
    key = get_settings().sbp_easydata_api_key
    if key is not None and key.get_secret_value():
        text = text.replace(key.get_secret_value(), "***")
    return text


def _save_raw(session: Session, run_id: int, payload: RawPayload) -> None:
    session.add(
        RawSnapshot(
            job_run_id=run_id,
            source=payload.source,
            url=redact(payload.url),
            content_type=payload.content_type,
            sha256=hashlib.sha256(payload.content).hexdigest(),
            size_bytes=len(payload.content),
            content=payload.content,
        )
    )
    session.commit()


def _validated(records: list[Record], provider: str) -> tuple[list[Record], int]:
    today = today_pkt()
    good: list[Record] = []
    skipped = 0
    for record in records:
        problem = record.validate(today)
        if problem:
            skipped += 1
            log.warning(
                "ingest.row_skipped", source=provider, reason=problem, record=repr(record)[:300]
            )
        else:
            good.append(record)
    return good, skipped


ABANDONED_AFTER = timedelta(hours=2)


def _close_abandoned(session: Session, source: str) -> None:
    """Mark runs left 'running' by a killed process as failed, so freshness stays truthful."""
    cutoff = datetime.now(UTC) - ABANDONED_AFTER
    session.execute(
        update(JobRun)
        .where(JobRun.source == source, JobRun.status == "running", JobRun.started_at < cutoff)
        .values(
            status="failed",
            finished_at=datetime.now(UTC),
            error="abandoned: the process exited before the run finished",
        )
    )
    session.commit()


def run_job(
    provider: Provider, session_factory: Callable[[], Session], ctx: FetchContext
) -> JobResult:
    params = {"as_of": ctx.as_of.isoformat(), "start": ctx.start.isoformat() if ctx.start else None}
    params.update(ctx.options)
    with session_factory() as session:
        _close_abandoned(session, provider.name)
        run = JobRun(source=provider.name, status="running", params=params)
        session.add(run)
        session.commit()
        run_id = run.id
        log.info("ingest.started", source=provider.name, job_run_id=run_id, **params)

        upserted = skipped = 0
        parse_failures = 0
        try:
            payloads = provider.fetch(ctx)
            for payload in payloads:
                _save_raw(session, run_id, payload)
                try:
                    records = list(provider.parse(payload))
                except Exception as exc:
                    parse_failures += 1
                    ctx.errors.append(f"parse {payload.url}: {exc!r}")
                    log.exception(
                        "ingest.parse_failed", source=provider.name, url=redact(payload.url)
                    )
                    continue
                good, bad = _validated(records, provider.name)
                skipped += bad
                upserted += write_records(session, good)
                session.commit()

            if ctx.errors:
                status = "partial" if (upserted or len(payloads) > parse_failures) else "failed"
            else:
                status = "success"
            error = redact("; ".join(ctx.errors))[:4000] or None
        except Exception as exc:
            session.rollback()
            status, error = "failed", redact(repr(exc))[:4000]
            log.error("ingest.failed", source=provider.name, job_run_id=run_id, error=error)

        run = session.get_one(JobRun, run_id)
        run.status = status
        run.rows_upserted = upserted
        run.rows_skipped = skipped
        run.error = error
        run.finished_at = datetime.now(UTC)
        session.commit()

    log.info(
        "ingest.finished",
        source=provider.name,
        job_run_id=run_id,
        status=status,
        rows_upserted=upserted,
        rows_skipped=skipped,
    )
    return JobResult(run_id, status, upserted, skipped, error)
