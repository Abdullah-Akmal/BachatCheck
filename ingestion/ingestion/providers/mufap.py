"""Mutual fund NAVs + trailing returns from MUFAP's "Performance Summary" Excel export.

MUFAP's site blocks automated requests and its Terms of Use allow personal, non-commercial use
only. So this provider never fetches from the web: you download the Excel export by hand from
https://www.mufap.com.pk/Industry/IndustryStatDaily?tab=1 and drop it in data/mufap_inbox/.
The live deployment shows demo fund data (FUNDS_DATA_MODE=demo), not MUFAP's.

Layout (checked against a real export on 2026-11-10): one title row, then a header row:
Sector | Category | Fund Name | Rating | Benchmark | Validity Date | NAV | YTD | MTD | 1 Day |
15 Days | 30 Days | 90 Days | 180 Days | 270 Days | 365 Days | 2 Years | 3 Years
"""

from __future__ import annotations

import io
import re
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import structlog

from bachatcheck.config import get_settings
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import FundSnapshotRecord, InstrumentRef, Record, to_decimal

log = structlog.get_logger()

SOURCE = "mufap"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

RETURN_COLUMNS = {
    "YTD": "ret_ytd",
    "MTD": "ret_mtd",
    "1 Day": "ret_1d",
    "15 Days": "ret_15d",
    "30 Days": "ret_30d",
    "90 Days": "ret_90d",
    "180 Days": "ret_180d",
    "270 Days": "ret_270d",
    "365 Days": "ret_365d",
    "2 Years": "ret_2y",
    "3 Years": "ret_3y",
}
REQUIRED = {"Sector", "Category", "Fund Name", "Validity Date", "NAV"}
_BASIS = re.compile(r"\((Annualized|Absolute) Return\s*\)", re.I)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def split_category(raw: str) -> tuple[str, str | None]:
    """'Money Market (Annualized Return )' -> ('Money Market', 'annualized')."""
    match = _BASIS.search(raw)
    basis = match.group(1).lower() if match else None
    return _BASIS.sub("", raw).strip(), basis


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip(), "%b %d, %Y").date()


class MufapProvider(Provider):
    name = "mufap"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        if path := ctx.options.get("file"):
            files = [Path(path)]
        else:
            inbox = get_settings().mufap_inbox_dir
            files = sorted(inbox.glob("*.xlsx")) if inbox.is_dir() else []
        if not files:
            raise FileNotFoundError(
                "No MUFAP export found. Download the Excel file from the MUFAP Performance "
                "Summary page and save it to data/mufap_inbox/ (or pass --file)."
            )
        return [
            RawPayload(
                source=self.name,
                url=f"file://{f.name}",
                content=f.read_bytes(),
                content_type=XLSX_TYPE,
            )
            for f in files
        ]

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(payload.content), read_only=True, data_only=True)
        rows = wb.worksheets[0].iter_rows(values_only=True)

        header: list[str] | None = None
        for row in rows:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if set(cells) >= REQUIRED:
                header = cells
                break
        if header is None:
            raise ValueError(f"no header row with columns {sorted(REQUIRED)}")
        col = {name: i for i, name in enumerate(header)}

        records: list[Record] = []
        for row in rows:
            if not row or row[col["Fund Name"]] in (None, ""):
                continue
            try:
                records.append(self._row(row, col))
            except (ValueError, TypeError) as exc:
                # Bad row: log and skip, don't fail the whole file.
                log.warning("mufap.bad_row", fund=row[col["Fund Name"]], error=str(exc))
        return records

    def _row(self, row: tuple[Any, ...], col: dict[str, int]) -> FundSnapshotRecord:
        name = str(row[col["Fund Name"]]).strip()
        category, basis = split_category(str(row[col["Category"]]))
        sector = str(row[col["Sector"]]).strip()
        rating = row[col["Rating"]] if "Rating" in col else None
        nav = to_decimal(row[col["NAV"]])
        if nav is None:
            raise ValueError("missing NAV")
        shariah = "shariah" in category.lower()
        instrument = InstrumentRef(
            kind="mutual_fund",
            symbol=slugify(name),
            name=name,
            source=SOURCE,
            category=category,
            sector=sector,
            rating=str(rating).strip() if rating not in (None, "") else None,
            is_shariah=shariah,
            return_basis=basis,
        )
        returns = {
            field: to_decimal(row[col[label]])
            for label, field in RETURN_COLUMNS.items()
            if label in col
        }
        return FundSnapshotRecord(
            instrument=instrument,
            as_of_date=parse_date(row[col["Validity Date"]]),
            nav=nav,
            source=SOURCE,
            returns=returns,
        )
