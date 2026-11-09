"""Shared response pieces. Decimals serialize as JSON strings so no precision is lost.

Money is rounded to 2 dp (PKR); returns are fractions rounded to 6 dp (0.126825 = 12.68%).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, PlainSerializer

from bachatcheck.returns.core import round_money, round_rate


def _money(v: Decimal | None) -> str | None:
    return None if v is None else str(round_money(v))


def _rate(v: Decimal | None) -> str | None:
    return None if v is None else str(round_rate(v))


Money = Annotated[Decimal | None, PlainSerializer(_money, return_type=str | None)]
Rate = Annotated[Decimal | None, PlainSerializer(_rate, return_type=str | None)]
# Values exactly as stored (e.g. NAVs, percent values from a source), no rounding.
Exact = Annotated[
    Decimal | None, PlainSerializer(lambda v: None if v is None else str(v), return_type=str | None)
]


class DataMeta(BaseModel):
    data_mode: str = "real"  # "real" | "demo"
    as_of: date | None = None
    source: str
    notes: list[str] = []
