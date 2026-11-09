from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bachatcheck import repo
from bachatcheck.api.v1.schemas import Money, Rate
from bachatcheck.clock import today_pkt
from bachatcheck.config import Settings, get_settings
from bachatcheck.db import get_session
from bachatcheck.returns.compare import (
    TBILL_TENORS,
    AssetResult,
    CompareInputs,
    on_grid,
    real_on_grid,
    run_compare,
)

router = APIRouter(tags=["compare"])


class TaxOut(BaseModel):
    status: str
    asset_class: str
    tax_type: str
    rate: Rate = None
    source_url: str | None = None


class AssetOut(BaseModel):
    key: str
    label: str
    group: str
    available: bool
    reason: str | None
    notes: list[str]
    demo: bool
    data_as_of: date | None
    path_kind: str
    end_value: Money
    nominal_return: Rate
    cagr: Rate
    real_end_value: Money
    real_return: Rate
    tax: TaxOut | None
    post_tax_end_value: Money
    post_tax_return: Rate
    post_tax_real_return: Rate
    nominal_series: list[Money]
    real_series: list[Money]


class Headline(BaseModel):
    amount: Money
    inflation: Rate
    inflation_cagr: Rate
    # What you'd need at the end to buy what `amount` bought at the start.
    amount_needed_to_keep_up: Money
    beat_inflation: list[str]
    lost_to_inflation: list[str]
    best_real: str | None


class CompareOut(BaseModel):
    amount: Money
    years: int
    start: date
    end: date
    shariah_only: bool
    filer_status: str
    cpi_as_of: date | None
    headline: Headline
    dates: list[date]
    inflation_series: list[Money]
    assets: list[AssetOut]
    disclaimer: str = (
        "For education only. Not investment advice. Data may be delayed or inaccurate."
    )


def load_inputs(s: Session, settings: Settings) -> CompareInputs:
    demo = settings.funds_data_mode == "demo"
    return CompareInputs(
        cpi_mom=repo.macro_points(s, "CPI_MOM"),
        savings_rates=repo.macro_points(s, settings.savings_benchmark_series),
        savings_series_code=settings.savings_benchmark_series,
        tbill_rates={code: repo.macro_points(s, code) for code, _, _ in TBILL_TENORS},
        index_prices={sym: repo.price_points(s, "index", sym) for sym in ("KSE100", "KMI30")},
        usd_pkr=repo.fx_points(s, "USD", "PKR"),
        gold=repo.price_points(s, "gold", "GOLD24K_TOLA"),
        funds=list(repo.demo_funds(settings.demo_funds_path)) if demo else repo.latest_funds(s),
        funds_demo=demo,
        tax_rules=repo.tax_rules(s),
    )


def _asset_out(a: AssetResult, dates: list[date], inp: CompareInputs, start: date) -> AssetOut:
    return AssetOut(
        key=a.key,
        label=a.label,
        group=a.group,
        available=a.available,
        reason=a.reason,
        notes=a.notes,
        demo=a.demo,
        data_as_of=a.data_as_of,
        path_kind=a.path_kind,
        end_value=a.end_value,
        nominal_return=a.nominal_return,
        cagr=a.cagr,
        real_end_value=a.real_end_value,
        real_return=a.real_return,
        tax=TaxOut(**vars(a.tax)) if a.tax else None,
        post_tax_end_value=a.post_tax_end_value,
        post_tax_return=a.post_tax_return,
        post_tax_real_return=a.post_tax_real_return,
        nominal_series=on_grid(a.path, dates) if a.available else [],
        real_series=real_on_grid(a.path, dates, inp.cpi_mom, start) if a.available else [],
    )


@router.get("/compare", response_model=CompareOut)
def compare(
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    amount: Annotated[
        Decimal, Query(gt=0, le=Decimal("100000000000"), description="PKR")
    ] = Decimal(100_000),
    years: Annotated[int, Query(ge=1, le=10)] = 1,
    shariah: bool = False,
    filer_status: Literal["filer", "non_filer"] = "filer",
    savings_rate: Annotated[
        Decimal | None, Query(ge=0, le=50, description="Your bank's annual profit rate, percent")
    ] = None,
    end: Annotated[date | None, Query(description="End date (default: today, PKT)")] = None,
) -> CompareOut:
    inp = load_inputs(s, settings)
    end_date = end or today_pkt()
    if end_date > today_pkt():
        raise HTTPException(422, "end can't be in the future")
    r = run_compare(inp, amount, years, end_date, shariah, filer_status, savings_rate)

    available = [a for a in r.assets if a.available and a.real_return is not None]
    beat = [a.key for a in available if a.real_return is not None and a.real_return > 0]
    lost = [a.key for a in available if a.real_return is not None and a.real_return <= 0]
    best = max(available, key=lambda a: a.real_return or Decimal(-1), default=None)

    return CompareOut(
        amount=r.amount,
        years=r.years,
        start=r.start,
        end=r.end,
        shariah_only=r.shariah_only,
        filer_status=r.filer_status,
        cpi_as_of=r.cpi_as_of,
        headline=Headline(
            amount=r.amount,
            inflation=r.inflation,
            inflation_cagr=r.inflation_cagr,
            amount_needed_to_keep_up=r.amount * (1 + r.inflation)
            if r.inflation is not None
            else None,
            beat_inflation=beat,
            lost_to_inflation=lost,
            best_real=best.key if best else None,
        ),
        dates=r.dates,
        inflation_series=r.inflation_series,
        assets=[_asset_out(a, r.dates, inp, r.start) for a in r.assets],
    )
