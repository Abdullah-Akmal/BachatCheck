"""Read queries used by the API. Returns plain dataclasses / point lists, never ORM objects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bachatcheck.models import (
    FundSnapshot,
    FxRate,
    Instrument,
    JobRun,
    MacroObservation,
    MacroSeries,
    PriceBar,
    TaxRule,
)
from bachatcheck.returns.series import Point

RETURN_FIELDS = (
    "ret_ytd",
    "ret_mtd",
    "ret_1d",
    "ret_15d",
    "ret_30d",
    "ret_90d",
    "ret_180d",
    "ret_270d",
    "ret_365d",
    "ret_2y",
    "ret_3y",
)


# --- Macro / FX / prices -------------------------------------------------------------


def macro_points(
    s: Session, code: str, start: date | None = None, end: date | None = None
) -> list[Point]:
    stmt = (
        select(MacroObservation.date, MacroObservation.value)
        .join(MacroSeries, MacroSeries.id == MacroObservation.series_id)
        .where(MacroSeries.code == code)
        .order_by(MacroObservation.date)
    )
    if start:
        stmt = stmt.where(MacroObservation.date >= start)
    if end:
        stmt = stmt.where(MacroObservation.date <= end)
    return [(d, v) for d, v in s.execute(stmt)]


@dataclass(frozen=True)
class SeriesInfo:
    code: str
    name: str
    unit: str
    frequency: str
    source: str
    first_date: date | None
    last_date: date | None
    observations: int


def macro_series_list(s: Session) -> list[SeriesInfo]:
    stmt = (
        select(
            MacroSeries.code,
            MacroSeries.name,
            MacroSeries.unit,
            MacroSeries.frequency,
            MacroSeries.source,
            func.min(MacroObservation.date),
            func.max(MacroObservation.date),
            func.count(MacroObservation.id),
        )
        .outerjoin(MacroObservation, MacroObservation.series_id == MacroSeries.id)
        .group_by(MacroSeries.id)
        .order_by(MacroSeries.code)
    )
    return [SeriesInfo(*row) for row in s.execute(stmt)]


def fx_points(s: Session, base: str = "USD", quote: str = "PKR") -> list[Point]:
    stmt = (
        select(FxRate.date, FxRate.rate)
        .where(FxRate.base == base, FxRate.quote == quote)
        .order_by(FxRate.date)
    )
    return [(d, v) for d, v in s.execute(stmt)]


def price_points(s: Session, kind: str, symbol: str, start: date | None = None) -> list[Point]:
    stmt = (
        select(PriceBar.date, PriceBar.close)
        .join(Instrument, Instrument.id == PriceBar.instrument_id)
        .where(Instrument.kind == kind, Instrument.symbol == symbol)
        .order_by(PriceBar.date)
    )
    if start:
        stmt = stmt.where(PriceBar.date >= start)
    return [(d, v) for d, v in s.execute(stmt)]


@dataclass(frozen=True)
class InstrumentInfo:
    kind: str
    symbol: str
    name: str
    is_shariah: bool | None
    first_date: date | None
    last_date: date | None


def search_instruments(
    s: Session, q: str, kinds: tuple[str, ...], limit: int = 20
) -> list[InstrumentInfo]:
    pattern = f"%{q.strip()}%"
    stmt = (
        select(
            Instrument.kind,
            Instrument.symbol,
            Instrument.name,
            Instrument.is_shariah,
            func.min(PriceBar.date),
            func.max(PriceBar.date),
        )
        .join(PriceBar, PriceBar.instrument_id == Instrument.id)
        .where(Instrument.kind.in_(kinds))
        .where((Instrument.symbol.ilike(pattern)) | (Instrument.name.ilike(pattern)))
        .group_by(Instrument.id)
        .order_by(Instrument.symbol)
        .limit(limit)
    )
    return [InstrumentInfo(*row) for row in s.execute(stmt)]


def instrument(s: Session, kinds: tuple[str, ...], symbol: str) -> InstrumentInfo | None:
    rows = search_instruments(s, symbol, kinds, limit=50)
    return next((r for r in rows if r.symbol == symbol.upper()), None)


# --- Funds -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FundRow:
    symbol: str
    name: str
    category: str
    sector: str | None
    amc: str | None
    rating: str | None
    is_shariah: bool
    return_basis: str | None
    as_of_date: date
    nav: Decimal
    returns: dict[str, Decimal | None] = field(default_factory=dict)


def _fund_row(inst: Instrument, snap: FundSnapshot) -> FundRow:
    return FundRow(
        symbol=inst.symbol,
        name=inst.name,
        category=inst.category or "Uncategorized",
        sector=inst.sector,
        amc=inst.amc,
        rating=inst.rating,
        is_shariah=bool(inst.is_shariah),
        return_basis=inst.return_basis,
        as_of_date=snap.as_of_date,
        nav=snap.nav,
        returns={f: getattr(snap, f) for f in RETURN_FIELDS},
    )


def latest_funds(s: Session) -> list[FundRow]:
    """Each fund's most recent snapshot."""
    latest = (
        select(FundSnapshot.instrument_id, func.max(FundSnapshot.as_of_date).label("d"))
        .group_by(FundSnapshot.instrument_id)
        .subquery()
    )
    stmt = (
        select(Instrument, FundSnapshot)
        .join(FundSnapshot, FundSnapshot.instrument_id == Instrument.id)
        .join(
            latest,
            (latest.c.instrument_id == FundSnapshot.instrument_id)
            & (latest.c.d == FundSnapshot.as_of_date),
        )
        .where(Instrument.kind == "mutual_fund")
        .order_by(Instrument.name)
    )
    return [_fund_row(i, f) for i, f in s.execute(stmt)]


def fund_history(s: Session, symbol: str) -> list[FundRow]:
    stmt = (
        select(Instrument, FundSnapshot)
        .join(FundSnapshot, FundSnapshot.instrument_id == Instrument.id)
        .where(Instrument.kind == "mutual_fund", Instrument.symbol == symbol)
        .order_by(FundSnapshot.as_of_date)
    )
    return [_fund_row(i, f) for i, f in s.execute(stmt)]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@lru_cache(maxsize=4)
def demo_funds(path: Path) -> tuple[FundRow, ...]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(doc["as_of_date"])
    rows = []
    for f in doc["funds"]:
        rows.append(
            FundRow(
                symbol=_slug(f["name"]),
                name=f["name"],
                category=f["category"],
                sector="Open-End Funds",
                amc=None,
                rating=f.get("rating"),
                is_shariah=bool(f["is_shariah"]),
                return_basis=f["return_basis"],
                as_of_date=as_of,
                nav=Decimal(f["nav"]),
                returns={
                    k: Decimal(f["returns"][k]) if k in f["returns"] else None
                    for k in RETURN_FIELDS
                },
            )
        )
    return tuple(rows)


# --- Operations / config ----------------------------------------------------------------


@dataclass(frozen=True)
class SourceFreshness:
    source: str
    last_success_at: datetime | None
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None


def freshness(s: Session) -> list[SourceFreshness]:
    last_ok = (
        select(JobRun.source, func.max(JobRun.finished_at).label("ok"))
        .where(JobRun.status.in_(("success", "partial")))
        .group_by(JobRun.source)
        .subquery()
    )
    last_any = (
        select(JobRun.source, func.max(JobRun.id).label("id")).group_by(JobRun.source).subquery()
    )
    stmt = (
        select(JobRun.source, last_ok.c.ok, JobRun.started_at, JobRun.status, JobRun.error)
        .join(last_any, last_any.c.id == JobRun.id)
        .outerjoin(last_ok, last_ok.c.source == JobRun.source)
        .order_by(JobRun.source)
    )
    return [SourceFreshness(*row) for row in s.execute(stmt)]


def data_dates(s: Session) -> dict[str, date | None]:
    """Latest data date per dataset, which is what users care about ("data as of")."""
    out: dict[str, date | None] = {}
    for code, d in s.execute(
        select(MacroSeries.code, func.max(MacroObservation.date))
        .join(MacroObservation, MacroObservation.series_id == MacroSeries.id)
        .group_by(MacroSeries.code)
    ):
        out[f"macro:{code}"] = d
    out["fx:USD/PKR"] = s.execute(select(func.max(FxRate.date))).scalar_one()
    for kind, d in s.execute(
        select(Instrument.kind, func.max(PriceBar.date))
        .join(PriceBar, PriceBar.instrument_id == Instrument.id)
        .group_by(Instrument.kind)
    ):
        out[f"prices:{kind}"] = d
    out["funds:mufap"] = s.execute(select(func.max(FundSnapshot.as_of_date))).scalar_one()
    return out


@dataclass(frozen=True)
class TaxRuleRow:
    asset_class: str
    tax_type: str
    filer_status: str
    rate: Decimal | None
    effective_from: date
    effective_to: date | None
    source_url: str | None
    notes: str | None
    verified: bool


def tax_rules(s: Session) -> list[TaxRuleRow]:
    stmt = select(TaxRule).order_by(TaxRule.asset_class, TaxRule.tax_type, TaxRule.effective_from)
    return [
        TaxRuleRow(
            r.asset_class,
            r.tax_type,
            r.filer_status,
            r.rate,
            r.effective_from,
            r.effective_to,
            r.source_url,
            r.notes,
            r.verified,
        )
        for r in s.execute(stmt).scalars()
    ]


def active_tax_rate(
    rules: list[TaxRuleRow], asset_class: str, tax_type: str, filer_status: str, on: date
) -> TaxRuleRow | None:
    """The rule in force on `on`, or None. A rule with rate=None/unverified is still returned."""
    candidates = [
        r
        for r in rules
        if r.asset_class == asset_class
        and r.tax_type == tax_type
        and r.filer_status == filer_status
        and r.effective_from <= on
        and (r.effective_to is None or r.effective_to >= on)
    ]
    return max(candidates, key=lambda r: r.effective_from, default=None)
