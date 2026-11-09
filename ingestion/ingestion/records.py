"""Normalized records that providers produce. Each validates itself before it is written.

All numeric values are Decimal. Providers convert at the boundary with `to_decimal`, which goes
through `str()` so a float like 10.83 becomes Decimal("10.83"), not 10.8300000000000000710...
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

# Pakistan has no DST, so a fixed UTC+5 offset is exact.
PKT = timezone(timedelta(hours=5), name="PKT")

# Sanity bounds. Values outside these are almost certainly parse errors.
MAX_ABS_PERCENT = Decimal("1000")  # trailing return / rate, in percent
MIN_DATE = date(1950, 1, 1)


def today_pkt() -> date:
    return datetime.now(PKT).date()


def to_decimal(value: Any) -> Decimal | None:
    """Convert a source value to Decimal. Blank / 'N/A' / NaN become None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return Decimal(repr(value))
    if isinstance(value, int):
        return Decimal(value)
    text = str(value).strip().replace(",", "")
    if text == "" or text.upper() in {"N/A", "NA", "-", "--", "NAN", "NULL"}:
        return None
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc
    return result if result.is_finite() else None


def _check_date(d: date, today: date) -> str | None:
    if d > today:
        return f"date {d} is in the future"
    if d < MIN_DATE:
        return f"date {d} is implausibly old"
    return None


@dataclass(frozen=True)
class InstrumentRef:
    kind: str
    symbol: str
    name: str
    source: str
    category: str | None = None
    sector: str | None = None
    amc: str | None = None
    rating: str | None = None
    is_shariah: bool | None = None
    return_basis: str | None = None
    currency: str = "PKR"


@dataclass(frozen=True)
class PriceBarRecord:
    instrument: InstrumentRef
    date: dt.date
    close: Decimal
    source: str
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None

    def validate(self, today: dt.date) -> str | None:
        if err := _check_date(self.date, today):
            return err
        prices = [p for p in (self.open, self.high, self.low, self.close) if p is not None]
        if any(p <= 0 for p in prices):
            return "non-positive price"
        if self.volume is not None and self.volume < 0:
            return "negative volume"
        if self.high is not None and self.low is not None:
            if self.low > self.high:
                return f"low {self.low} > high {self.high}"
            for name, p in (("open", self.open), ("close", self.close)):
                if p is not None and not (self.low <= p <= self.high):
                    return f"{name} {p} outside low/high [{self.low}, {self.high}]"
        return None


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


@dataclass(frozen=True)
class FundSnapshotRecord:
    instrument: InstrumentRef
    as_of_date: date
    nav: Decimal
    source: str
    # Keys from RETURN_FIELDS; values are percent (10.83 = 10.83%).
    returns: dict[str, Decimal | None] = field(default_factory=dict)

    def validate(self, today: dt.date) -> str | None:
        if err := _check_date(self.as_of_date, today):
            return err
        if self.nav <= 0:
            return f"NAV {self.nav} is not positive"
        for key, value in self.returns.items():
            if key not in RETURN_FIELDS:
                return f"unknown return field {key}"
            if value is not None and abs(value) > MAX_ABS_PERCENT:
                return f"{key}={value}% is outside sanity bounds"
        return None


@dataclass(frozen=True)
class MacroSeriesDef:
    code: str
    name: str
    unit: str
    frequency: str
    source: str
    source_key: str
    description: str | None = None


@dataclass(frozen=True)
class MacroObservationRecord:
    series: MacroSeriesDef
    date: dt.date
    value: Decimal
    source: str
    status: str | None = None

    def validate(self, today: dt.date) -> str | None:
        if err := _check_date(self.date, today):
            return err
        if self.series.unit.lower() == "percent" and abs(self.value) > MAX_ABS_PERCENT:
            return f"{self.value}% is outside sanity bounds"
        return None


@dataclass(frozen=True)
class FxRateRecord:
    base: str
    quote: str
    date: dt.date
    rate: Decimal
    provider: str

    def validate(self, today: dt.date) -> str | None:
        if err := _check_date(self.date, today):
            return err
        if self.rate <= 0:
            return f"rate {self.rate} is not positive"
        if len(self.base) != 3 or len(self.quote) != 3:
            return "currency codes must be 3 letters"
        return None


@dataclass(frozen=True)
class TaxRuleRecord:
    asset_class: str
    tax_type: str
    filer_status: str
    effective_from: date
    rate: Decimal | None
    effective_to: date | None = None
    source_url: str | None = None
    notes: str | None = None
    verified: bool = False

    def validate(self, today: dt.date) -> str | None:
        if self.rate is not None and not (Decimal(0) <= self.rate <= Decimal(1)):
            return f"rate {self.rate} must be a fraction between 0 and 1"
        if self.verified and self.rate is None:
            return "a verified rule must have a rate"
        if self.effective_to is not None and self.effective_to < self.effective_from:
            return "effective_to is before effective_from"
        return None


Record = PriceBarRecord | FundSnapshotRecord | MacroObservationRecord | FxRateRecord | TaxRuleRecord
