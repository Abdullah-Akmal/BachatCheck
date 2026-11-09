"""Investable instruments and their price / NAV history."""

from datetime import date
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bachatcheck.db import Base
from bachatcheck.models.types import CreatedAt, Money, MoneyOpt, PercentOpt, UpdatedAt

INSTRUMENT_KINDS = ("stock", "index", "mutual_fund", "gold")


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("kind", "symbol", name="uq_instruments_kind_symbol"),
        CheckConstraint(
            "kind IN ('stock', 'index', 'mutual_fund', 'gold')", name="instrument_kind"
        ),
        CheckConstraint(
            "return_basis IS NULL OR return_basis IN ('annualized', 'absolute')",
            name="instrument_return_basis",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    symbol: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120))
    sector: Mapped[str | None] = mapped_column(String(80))
    amc: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[str | None] = mapped_column(String(20))
    is_shariah: Mapped[bool | None]
    # How MUFAP reports this fund's trailing returns.
    return_basis: Mapped[str | None] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3), default="PKR")
    source: Mapped[str] = mapped_column(String(40))
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class PriceBar(Base):
    """Daily OHLCV for stocks, indices and gold (gold has close only)."""

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "date", "source", name="uq_price_bars_inst_date_src"),
        CheckConstraint("close > 0", name="price_bar_close_positive"),
        Index("ix_price_bars_inst_date", "instrument_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    date: Mapped[date]
    open: Mapped[MoneyOpt]
    high: Mapped[MoneyOpt]
    low: Mapped[MoneyOpt]
    close: Mapped[Money]
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[UpdatedAt]


class FundSnapshot(Base):
    """One MUFAP daily row: NAV plus trailing returns (percent) as of the fund's validity date."""

    __tablename__ = "fund_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "as_of_date", "source", name="uq_fund_snapshots_inst_date_src"
        ),
        CheckConstraint("nav > 0", name="fund_snapshot_nav_positive"),
        Index("ix_fund_snapshots_inst_date", "instrument_id", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    as_of_date: Mapped[date]
    nav: Mapped[Money]
    ret_ytd: Mapped[PercentOpt]
    ret_mtd: Mapped[PercentOpt]
    ret_1d: Mapped[PercentOpt]
    ret_15d: Mapped[PercentOpt]
    ret_30d: Mapped[PercentOpt]
    ret_90d: Mapped[PercentOpt]
    ret_180d: Mapped[PercentOpt]
    ret_270d: Mapped[PercentOpt]
    ret_365d: Mapped[PercentOpt]
    ret_2y: Mapped[PercentOpt]
    ret_3y: Mapped[PercentOpt]
    source: Mapped[str] = mapped_column(String(40))
    ingested_at: Mapped[UpdatedAt]
