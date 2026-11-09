"""Shared column types. Money and rates are always NUMERIC, mapped to Python Decimal."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import mapped_column

# Prices / NAVs: up to 14 integer digits, 6 decimals.
Money = Annotated[Decimal, mapped_column(Numeric(20, 6))]
MoneyOpt = Annotated[Decimal | None, mapped_column(Numeric(20, 6))]
# Percent values (e.g. 10.83 means 10.83%).
Percent = Annotated[Decimal, mapped_column(Numeric(12, 6))]
PercentOpt = Annotated[Decimal | None, mapped_column(Numeric(12, 6))]

CreatedAt = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    ),
]
