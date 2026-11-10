"""Idempotent upserts. Re-running a job for the same date updates rows, never duplicates them."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bachatcheck.models import (
    FundSnapshot,
    FxRate,
    Instrument,
    MacroObservation,
    MacroSeries,
    PriceBar,
    TaxRule,
)
from ingestion.records import (
    RETURN_FIELDS,
    FundSnapshotRecord,
    FxRateRecord,
    InstrumentRef,
    MacroObservationRecord,
    MacroSeriesDef,
    PriceBarRecord,
    Record,
    TaxRuleRecord,
)


class _Cache:
    def __init__(self) -> None:
        self.instruments: dict[tuple[str, str], int] = {}
        self.series: dict[str, int] = {}


def _instrument_id(session: Session, ref: InstrumentRef, cache: _Cache) -> int:
    key = (ref.kind, ref.symbol)
    if key in cache.instruments:
        return cache.instruments[key]
    values: dict[str, Any] = {
        "kind": ref.kind,
        "symbol": ref.symbol,
        "name": ref.name,
        "category": ref.category,
        "sector": ref.sector,
        "amc": ref.amc,
        "rating": ref.rating,
        "is_shariah": ref.is_shariah,
        "return_basis": ref.return_basis,
        "currency": ref.currency,
        "source": ref.source,
        "extra": {},
    }
    updatable = {k: v for k, v in values.items() if k not in ("kind", "symbol", "extra")}
    stmt = (
        insert(Instrument)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_instruments_kind_symbol",
            set_={**updatable, "updated_at": func.now()},
        )
        .returning(Instrument.id)
    )
    inst_id = int(session.execute(stmt).scalar_one())
    cache.instruments[key] = inst_id
    return inst_id


def _series_id(session: Session, s: MacroSeriesDef, cache: _Cache) -> int:
    if s.code in cache.series:
        return cache.series[s.code]
    values = {
        "code": s.code,
        "name": s.name,
        "unit": s.unit,
        "frequency": s.frequency,
        "source": s.source,
        "source_key": s.source_key,
        "description": s.description,
    }
    stmt = (
        insert(MacroSeries)
        .values(**values)
        .on_conflict_do_update(index_elements=["code"], set_=values)
        .returning(MacroSeries.id)
    )
    sid = int(session.execute(stmt).scalar_one())
    cache.series[s.code] = sid
    return sid


# Postgres allows at most 65,535 bind parameters per statement; 1,000 rows x ~15 columns is safe.
CHUNK_ROWS = 1000


def _upsert(session: Session, model: Any, rows: list[dict[str, Any]], constraint: str) -> int:
    if not rows:
        return 0
    table = model.__table__
    unique = next(c for c in table.constraints if c.name == constraint)
    key_cols = {col.name for col in unique.columns}
    for start in range(0, len(rows), CHUNK_ROWS):
        stmt = insert(model).values(rows[start : start + CHUNK_ROWS])
        update = {
            c.name: stmt.excluded[c.name]
            for c in table.columns
            if c.name not in key_cols and c.name != "id" and c.name in rows[0]
        }
        for stamp in ("ingested_at", "updated_at"):
            if stamp in table.columns:
                update[stamp] = func.now()
        session.execute(stmt.on_conflict_do_update(constraint=constraint, set_=update))
    return len(rows)


def _dedupe(rows: list[dict[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    """Postgres rejects one INSERT that hits the same conflict key twice; keep the last row."""
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        seen[tuple(row[k] for k in keys)] = row
    return list(seen.values())


def write_records(session: Session, records: Sequence[Record]) -> int:
    """Upsert a batch of validated records. Returns the number of rows written."""
    cache = _Cache()
    bars: list[dict[str, Any]] = []
    funds: list[dict[str, Any]] = []
    macro: list[dict[str, Any]] = []
    fx: list[dict[str, Any]] = []
    tax: list[dict[str, Any]] = []

    for r in records:
        if isinstance(r, PriceBarRecord):
            bars.append(
                {
                    "instrument_id": _instrument_id(session, r.instrument, cache),
                    "date": r.date,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                    "source": r.source,
                }
            )
        elif isinstance(r, FundSnapshotRecord):
            funds.append(
                {
                    "instrument_id": _instrument_id(session, r.instrument, cache),
                    "as_of_date": r.as_of_date,
                    "nav": r.nav,
                    "source": r.source,
                    **{k: r.returns.get(k) for k in RETURN_FIELDS},
                }
            )
        elif isinstance(r, MacroObservationRecord):
            macro.append(
                {
                    "series_id": _series_id(session, r.series, cache),
                    "date": r.date,
                    "value": r.value,
                    "status": r.status,
                    "source": r.source,
                }
            )
        elif isinstance(r, FxRateRecord):
            fx.append(
                {
                    "base": r.base,
                    "quote": r.quote,
                    "date": r.date,
                    "rate": r.rate,
                    "provider": r.provider,
                }
            )
        elif isinstance(r, TaxRuleRecord):
            tax.append(
                {
                    "asset_class": r.asset_class,
                    "tax_type": r.tax_type,
                    "filer_status": r.filer_status,
                    "rate": r.rate,
                    "effective_from": r.effective_from,
                    "effective_to": r.effective_to,
                    "source_url": r.source_url,
                    "notes": r.notes,
                    "verified": r.verified,
                }
            )

    n = 0
    n += _upsert(
        session,
        PriceBar,
        _dedupe(bars, ("instrument_id", "date", "source")),
        "uq_price_bars_inst_date_src",
    )
    n += _upsert(
        session,
        FundSnapshot,
        _dedupe(funds, ("instrument_id", "as_of_date", "source")),
        "uq_fund_snapshots_inst_date_src",
    )
    n += _upsert(
        session,
        MacroObservation,
        _dedupe(macro, ("series_id", "date", "source")),
        "uq_macro_obs_series_date_src",
    )
    n += _upsert(
        session,
        FxRate,
        _dedupe(fx, ("base", "quote", "date", "provider")),
        "uq_fx_rates_pair_date_prov",
    )
    n += _upsert(
        session,
        TaxRule,
        _dedupe(tax, ("asset_class", "tax_type", "filer_status", "effective_from")),
        "uq_tax_rules_class_type_filer_from",
    )
    return n
