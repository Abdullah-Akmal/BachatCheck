"""PSX stock lookup: price history and return vs the KSE-100 over the same dates."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bachatcheck import repo
from bachatcheck.api.v1.schemas import DataMeta, Exact, Rate
from bachatcheck.clock import today_pkt
from bachatcheck.config import Settings, get_settings
from bachatcheck.db import get_session
from bachatcheck.returns.core import absolute_return, cagr
from bachatcheck.returns.series import add_months, value_on_or_before

router = APIRouter(prefix="/stocks", tags=["stocks"])
KINDS = ("stock", "index")
BENCHMARK = "KSE100"
Period = Literal["1m", "3m", "6m", "1y", "3y", "5y", "max"]
PERIOD_MONTHS = {"1m": 1, "3m": 3, "6m": 6, "1y": 12, "3y": 36, "5y": 60}


class InstrumentOut(BaseModel):
    kind: str
    symbol: str
    name: str
    is_shariah: bool | None
    first_date: date | None
    last_date: date | None


class PerformanceOut(BaseModel):
    start: date
    end: date
    start_price: Exact
    end_price: Exact
    total_return: Rate
    cagr: Rate


class StockOut(BaseModel):
    meta: DataMeta
    instrument: InstrumentOut
    period: str
    requested_start: date
    # True when our price history starts after `requested_start`, so the figures cover less
    # than the chosen period. The UI must say so rather than present it as e.g. a 1-year return.
    partial: bool
    prices: list[tuple[date, Exact]]
    performance: PerformanceOut | None
    benchmark: PerformanceOut | None
    benchmark_symbol: str
    # Both series rebased to 100 at the start, for an apples-to-apples chart.
    rebased: list[tuple[date, Rate, Rate]]


def _ensure_enabled(settings: Settings) -> None:
    if settings.stocks_data_mode == "demo":
        raise HTTPException(503, "Stock data is disabled on this deployment.")


def _perf(points: list[tuple[date, Decimal]], start: date, end: date) -> PerformanceOut | None:
    a = next(((d, v) for d, v in points if d >= start), None)
    b = value_on_or_before(points, end)
    if a is None or b is None or b[0] <= a[0]:
        return None
    total = absolute_return(a[1], b[1])
    return PerformanceOut(
        start=a[0],
        end=b[0],
        start_price=a[1],
        end_price=b[1],
        total_return=total,
        cagr=cagr(total, (b[0] - a[0]).days) if (b[0] - a[0]).days >= 365 else None,
    )


@router.get("/search", response_model=list[InstrumentOut])
def search(
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query(min_length=1, max_length=40)],
) -> list[InstrumentOut]:
    _ensure_enabled(settings)
    return [InstrumentOut(**vars(i)) for i in repo.search_instruments(s, q, KINDS)]


@router.get("/{symbol}", response_model=StockOut)
def stock(
    symbol: str,
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    period: Period = "1y",
) -> StockOut:
    _ensure_enabled(settings)
    info = repo.instrument(s, KINDS, symbol)
    if info is None:
        raise HTTPException(404, f"symbol '{symbol.upper()}' not found")
    end = info.last_date or today_pkt()
    start = add_months(end, -PERIOD_MONTHS[period]) if period != "max" else (info.first_date or end)

    prices = repo.price_points(s, info.kind, info.symbol, start)
    bench = prices if info.symbol == BENCHMARK else repo.price_points(s, "index", BENCHMARK, start)
    perf = _perf(prices, start, end)
    bench_perf = _perf(bench, start, end)

    rebased: list[tuple[date, Decimal | None, Decimal | None]] = []
    if prices and bench:
        p0, b0 = prices[0][1], bench[0][1]
        for d, v in prices:
            bv = value_on_or_before(bench, d)
            rebased.append((d, v / p0 * 100, bv[1] / b0 * 100 if bv else None))

    return StockOut(
        meta=DataMeta(
            as_of=info.last_date,
            source="PSX via psxdata (unofficial)",
            notes=["Price returns only; dividends aren't included."],
        ),
        instrument=InstrumentOut(**vars(info)),
        period=period,
        requested_start=start,
        # Allow a week of slack for weekends/holidays at the start of the window.
        partial=not prices or (prices[0][0] - start).days > 7,
        prices=prices,
        performance=perf,
        benchmark=bench_perf,
        benchmark_symbol=BENCHMARK,
        rebased=rebased,
    )
