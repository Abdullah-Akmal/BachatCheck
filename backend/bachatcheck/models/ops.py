"""Operational tables: raw source payloads and ingestion job runs."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bachatcheck.db import Base

JOB_STATUSES = ("running", "success", "partial", "failed")


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')", name="job_run_status"
        ),
        Index("ix_job_runs_source_started", "source", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="running")
    rows_upserted: Mapped[int] = mapped_column(default=0)
    rows_skipped: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class RawSnapshot(Base):
    """Exact bytes a source returned, saved before parsing so a parser bug never loses data."""

    __tablename__ = "raw_snapshots"
    __table_args__ = (Index("ix_raw_snapshots_source_fetched", "source", "fetched_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_run_id: Mapped[int | None] = mapped_column(ForeignKey("job_runs.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(40))
    # Secrets (e.g. API keys) are stripped from this URL before it is stored.
    url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    content_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int]
    content: Mapped[bytes] = mapped_column(LargeBinary)
