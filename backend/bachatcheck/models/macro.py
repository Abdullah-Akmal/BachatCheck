"""Macro series (CPI, policy rate, T-bill yields, KIBOR, deposit rates) and FX rates."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bachatcheck.db import Base
from bachatcheck.models.types import UpdatedAt


class MacroSeries(Base):
    __tablename__ = "macro_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Our stable code, e.g. "CPI_YOY". Never changes even if the upstream key does.
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(40))
    frequency: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(40))
    source_key: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (
        UniqueConstraint("series_id", "date", "source", name="uq_macro_obs_series_date_src"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("macro_series.id", ondelete="CASCADE"))
    date: Mapped[date]
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    status: Mapped[str | None] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[UpdatedAt]


class FxRate(Base):
    """`rate` units of `quote` per 1 `base` (e.g. base=USD, quote=PKR, rate=277.41)."""

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("base", "quote", "date", "provider", name="uq_fx_rates_pair_date_prov"),
        CheckConstraint("rate > 0", name="fx_rate_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    base: Mapped[str] = mapped_column(String(3))
    quote: Mapped[str] = mapped_column(String(3))
    date: Mapped[date]
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    provider: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[UpdatedAt]
