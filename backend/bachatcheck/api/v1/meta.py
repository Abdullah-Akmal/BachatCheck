"""Macro series, data freshness, tax assumptions and app config for the methodology page."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from bachatcheck import repo
from bachatcheck.api.v1.schemas import Exact
from bachatcheck.config import Settings, get_settings
from bachatcheck.db import get_session

router = APIRouter(tags=["meta"])


class SeriesOut(BaseModel):
    code: str
    name: str
    unit: str
    frequency: str
    source: str
    first_date: date | None
    last_date: date | None
    observations: int


class SeriesDataOut(BaseModel):
    series: SeriesOut
    points: list[tuple[date, Exact]]


class SourceOut(BaseModel):
    source: str
    last_success_at: datetime | None
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None


class FreshnessOut(BaseModel):
    sources: list[SourceOut]
    data_as_of: dict[str, date | None]


class TaxRuleOut(BaseModel):
    asset_class: str
    tax_type: str
    filer_status: str
    rate: Exact
    effective_from: date
    effective_to: date | None
    source_url: str | None
    notes: str | None
    verified: bool


class ConfigOut(BaseModel):
    funds_data_mode: str
    stocks_data_mode: str
    savings_benchmark_series: str
    # True when the database holds synthetic rows from `ingestion seed`; the UI shows a banner.
    synthetic_data: bool


@router.get("/macro", response_model=list[SeriesOut])
def macro_series(s: Annotated[Session, Depends(get_session)]) -> list[SeriesOut]:
    return [SeriesOut(**vars(i)) for i in repo.macro_series_list(s)]


@router.get("/macro/{code}", response_model=SeriesDataOut)
def macro_data(
    code: str,
    s: Annotated[Session, Depends(get_session)],
    start: date | None = None,
    end: date | None = None,
) -> SeriesDataOut:
    info = next((i for i in repo.macro_series_list(s) if i.code == code.upper()), None)
    if info is None:
        raise HTTPException(404, f"series '{code}' not found")
    return SeriesDataOut(
        series=SeriesOut(**vars(info)), points=repo.macro_points(s, info.code, start, end)
    )


@router.get("/freshness", response_model=FreshnessOut)
def freshness(s: Annotated[Session, Depends(get_session)]) -> FreshnessOut:
    """When each source last ran, and how recent its data is. Errors are already redacted."""
    return FreshnessOut(
        sources=[SourceOut(**vars(f)) for f in repo.freshness(s)],
        data_as_of=repo.data_dates(s),
    )


@router.get("/tax-rules", response_model=list[TaxRuleOut])
def tax_rules(s: Annotated[Session, Depends(get_session)]) -> list[TaxRuleOut]:
    return [TaxRuleOut(**vars(r)) for r in repo.tax_rules(s)]


@router.get("/config", response_model=ConfigOut)
def config(
    settings: Annotated[Settings, Depends(get_settings)],
    s: Annotated[Session, Depends(get_session)],
) -> ConfigOut:
    return ConfigOut(
        funds_data_mode=settings.funds_data_mode,
        stocks_data_mode=settings.stocks_data_mode,
        savings_benchmark_series=settings.savings_benchmark_series,
        synthetic_data=repo.has_synthetic_data(s),
    )
