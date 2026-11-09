"""Mutual funds explorer. In demo mode, serves synthetic funds instead of MUFAP data."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bachatcheck import repo
from bachatcheck.api.v1.schemas import DataMeta, Exact
from bachatcheck.config import Settings, get_settings
from bachatcheck.db import get_session

router = APIRouter(prefix="/funds", tags=["funds"])

SortKey = Literal[
    "name", "category", "nav", "ret_ytd", "ret_mtd",
    "ret_30d", "ret_90d", "ret_365d", "ret_2y", "ret_3y",
]  # fmt: skip


class FundOut(BaseModel):
    symbol: str
    name: str
    category: str
    sector: str | None
    amc: str | None
    rating: str | None
    is_shariah: bool
    # How returns are quoted: "annualized" (money market/income) or "absolute" (equity etc.).
    return_basis: str | None
    as_of_date: date
    nav: Exact
    # Percent values as published (10.83 = 10.83%).
    ret_ytd: Exact = None
    ret_mtd: Exact = None
    ret_1d: Exact = None
    ret_15d: Exact = None
    ret_30d: Exact = None
    ret_90d: Exact = None
    ret_180d: Exact = None
    ret_270d: Exact = None
    ret_365d: Exact = None
    ret_2y: Exact = None
    ret_3y: Exact = None


class FundsOut(BaseModel):
    meta: DataMeta
    total: int
    funds: list[FundOut]


class CategoryOut(BaseModel):
    category: str
    is_shariah: bool
    return_basis: str | None
    count: int


class FundDetailOut(BaseModel):
    meta: DataMeta
    fund: FundOut
    # One point per ingested MUFAP snapshot; history grows as daily snapshots accumulate.
    nav_history: list[tuple[date, Exact]]


def _out(f: repo.FundRow) -> FundOut:
    return FundOut(
        symbol=f.symbol,
        name=f.name,
        category=f.category,
        sector=f.sector,
        amc=f.amc,
        rating=f.rating,
        is_shariah=f.is_shariah,
        return_basis=f.return_basis,
        as_of_date=f.as_of_date,
        nav=f.nav,
        **f.returns,
    )


def _funds(s: Session, settings: Settings) -> tuple[list[repo.FundRow], DataMeta]:
    if settings.funds_data_mode == "demo":
        rows = list(repo.demo_funds(settings.demo_funds_path))
        meta = DataMeta(
            data_mode="demo",
            as_of=max((r.as_of_date for r in rows), default=None),
            source="Synthetic demo data",
            notes=[
                "These funds and numbers are made up for illustration.",
                "Real MUFAP data isn't shown publicly: MUFAP's terms require written approval.",
            ],
        )
    else:
        rows = repo.latest_funds(s)
        meta = DataMeta(
            data_mode="real",
            as_of=max((r.as_of_date for r in rows), default=None),
            source="MUFAP Performance Summary (manually downloaded export)",
        )
    return rows, meta


@router.get("", response_model=FundsOut)
def list_funds(
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    category: str | None = None,
    shariah: bool | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    sort: SortKey = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> FundsOut:
    rows, meta = _funds(s, settings)
    if category:
        rows = [r for r in rows if r.category == category]
    if shariah is not None:
        rows = [r for r in rows if r.is_shariah == shariah]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r.name.lower() or needle in (r.amc or "").lower()]

    def key(r: repo.FundRow) -> tuple[bool, object]:
        value: object = (
            getattr(r, sort) if sort in ("name", "category", "nav") else r.returns.get(sort)
        )
        # Missing values sort last in both directions.
        return (value is None) != (order == "desc"), value if value is not None else 0

    rows.sort(key=key, reverse=order == "desc")
    return FundsOut(meta=meta, total=len(rows), funds=[_out(r) for r in rows[:limit]])


@router.get("/categories", response_model=list[CategoryOut])
def categories(
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CategoryOut]:
    rows, _ = _funds(s, settings)
    grouped: dict[str, list[repo.FundRow]] = {}
    for r in rows:
        grouped.setdefault(r.category, []).append(r)
    return [
        CategoryOut(
            category=c, is_shariah=fs[0].is_shariah, return_basis=fs[0].return_basis, count=len(fs)
        )
        for c, fs in sorted(grouped.items())
    ]


@router.get("/{symbol}", response_model=FundDetailOut)
def fund_detail(
    symbol: str,
    s: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FundDetailOut:
    if settings.funds_data_mode == "demo":
        rows, meta = _funds(s, settings)
        history = [r for r in rows if r.symbol == symbol]
    else:
        history = repo.fund_history(s, symbol)
        meta = DataMeta(
            data_mode="real",
            as_of=history[-1].as_of_date if history else None,
            source="MUFAP Performance Summary (manually downloaded export)",
        )
    if not history:
        raise HTTPException(404, f"fund '{symbol}' not found")
    return FundDetailOut(
        meta=meta,
        fund=_out(history[-1]),
        nav_history=[(h.as_of_date, h.nav) for h in history],
    )
