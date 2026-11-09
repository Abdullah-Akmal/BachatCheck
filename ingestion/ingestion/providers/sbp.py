"""Macro series from SBP EasyData: CPI, policy rate, T-bill yields, KIBOR, deposit rates.

API: GET https://easydata.sbp.org.pk/api/v1/series/{series_key}/data
     ?api_key=...&format=json&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
Limits: 2,000 requests/day, 250/hour. API keys expire every 90 days.
The key only works as a query parameter, so it is added at request time and never stored.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta
from urllib.parse import urlencode

import httpx
import structlog

from bachatcheck.config import get_settings
from ingestion import http
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import MacroObservationRecord, MacroSeriesDef, Record, to_decimal

log = structlog.get_logger()

BASE_URL = "https://easydata.sbp.org.pk/api/v1/series"
NORMAL_WINDOW = timedelta(days=120)


def _s(
    code: str, key: str, name: str, unit: str, freq: str, desc: str | None = None
) -> MacroSeriesDef:
    return MacroSeriesDef(code, name, unit, freq, "sbp_easydata", key, desc)


# Our stable codes -> SBP series keys (verified against /dataset/{code}/meta on 2026-11-10).
SERIES: tuple[MacroSeriesDef, ...] = (
    _s("CPI_YOY", "TS_GP_PT_CPI_M.P00011516", "National CPI inflation (YoY)", "Percent", "monthly"),
    _s(
        "CPI_MOM",
        "TS_GP_PT_CPI_M.P00461516",
        "National CPI inflation (MoM)",
        "Percent",
        "monthly",
        "Chained into a price index for exact real-return compounding.",
    ),
    _s(
        "POLICY_RATE",
        "TS_GP_IR_SIRPR_AH.SBPOL0030",
        "SBP policy (target) rate",
        "Percent",
        "as-needed",
    ),
    _s(
        "TBILL_3M",
        "TS_GP_BAM_SIRTBIL_AH.TB0010",
        "T-bill cut-off yield, 3 months",
        "Percent",
        "as-needed",
    ),
    _s(
        "TBILL_6M",
        "TS_GP_BAM_SIRTBIL_AH.TB0020",
        "T-bill cut-off yield, 6 months",
        "Percent",
        "as-needed",
    ),
    _s(
        "TBILL_12M",
        "TS_GP_BAM_SIRTBIL_AH.TB0030",
        "T-bill cut-off yield, 12 months",
        "Percent",
        "as-needed",
    ),
    _s(
        "KIBOR_3M",
        "TS_GP_BAM_SIRKIBOR_D.KIBOR0020",
        "KIBOR offer rate, 3 months",
        "Percent",
        "daily",
    ),
    _s(
        "KIBOR_6M",
        "TS_GP_BAM_SIRKIBOR_D.KIBOR0030",
        "KIBOR offer rate, 6 months",
        "Percent",
        "daily",
    ),
    # NOTE: TS_GP_BAM_WALDR_M (the detailed bank-type breakdown) has had only blank
    # "Missing value" rows since 2024, so we use the overall SIRWALDR series instead. These
    # averages include zero-profit current accounts, so they understate savings-account rates.
    _s(
        "DEPOSIT_RATE_FRESH",
        "TS_GP_BAM_SIRWALDR_M.WALD0030",
        "Weighted avg. deposit rate, fresh (marginal) deposits, overall",
        "Percent",
        "monthly",
        "Includes zero-markup deposits.",
    ),
    _s(
        "DEPOSIT_RATE_OUTSTANDING",
        "TS_GP_BAM_SIRWALDR_M.WALD0040",
        "Weighted avg. deposit rate, outstanding deposits, overall",
        "Percent",
        "monthly",
        "Includes zero-markup deposits.",
    ),
)
BY_KEY = {s.source_key: s for s in SERIES}

# Column names as returned by the API (checked against a live response).
COL_KEY, COL_DATE, COL_VALUE, COL_STATUS = (
    "Series Key",
    "Observation Date",
    "Observation Value",
    "Observation Status",
)


class SbpProvider(Provider):
    name = "sbp"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        key = get_settings().sbp_easydata_api_key
        if key is None or not key.get_secret_value():
            raise RuntimeError(
                "SBP_EASYDATA_API_KEY is not set. Generate one at easydata.sbp.org.pk "
                "(My Data Basket -> My Account -> Generate API Key); keys expire after 90 days."
            )
        start = ctx.start or ctx.as_of - NORMAL_WINDOW
        only = set(filter(None, ctx.options.get("series", "").split(",")))
        payloads = []
        with http.make_client() as client:
            for s in SERIES:
                if only and s.code not in only:
                    continue
                public = {
                    "format": "json",
                    "start_date": start.isoformat(),
                    "end_date": ctx.as_of.isoformat(),
                }
                url = f"{BASE_URL}/{s.source_key}/data"
                try:
                    resp = http.get(client, url, {**public, "api_key": key.get_secret_value()})
                except httpx.HTTPError as exc:
                    # One bad series shouldn't sink the others.
                    status = getattr(getattr(exc, "response", None), "status_code", "?")
                    ctx.errors.append(f"{s.code}: HTTP {status} ({type(exc).__name__})")
                    log.warning("sbp.series_failed", series=s.code, status=status)
                    continue
                payloads.append(
                    RawPayload(
                        source=self.name,
                        url=f"{url}?{urlencode(public)}",  # no api_key
                        content=resp.content,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
                )
        return payloads

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        data = json.loads(payload.content)
        columns: list[str] = data["columns"]
        idx = {name: i for i, name in enumerate(columns)}
        missing = {COL_KEY, COL_DATE, COL_VALUE} - idx.keys()
        if missing:
            raise ValueError(f"SBP response missing columns: {sorted(missing)}")

        records: list[Record] = []
        for row in data["rows"]:
            series = BY_KEY.get(row[idx[COL_KEY]])
            if series is None:
                log.warning("sbp.unknown_series", key=row[idx[COL_KEY]])
                continue
            value = to_decimal(row[idx[COL_VALUE]])
            if value is None:
                log.info("sbp.blank_value", series=series.code, date=row[idx[COL_DATE]])
                continue
            records.append(
                MacroObservationRecord(
                    series=series,
                    date=date.fromisoformat(row[idx[COL_DATE]]),
                    value=value,
                    status=row[idx[COL_STATUS]] if COL_STATUS in idx else None,
                    source="sbp_easydata",
                )
            )
        return records
