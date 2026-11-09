"""Versioned tax assumptions. Rates are data loaded from data/tax_rules.yaml, never code."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bachatcheck.db import Base
from bachatcheck.models.types import UpdatedAt


class TaxRule(Base):
    __tablename__ = "tax_rules"
    __table_args__ = (
        UniqueConstraint(
            "asset_class",
            "tax_type",
            "filer_status",
            "effective_from",
            name="uq_tax_rules_class_type_filer_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(40))
    tax_type: Mapped[str] = mapped_column(String(60))
    filer_status: Mapped[str] = mapped_column(String(20), default="filer")
    # Fraction, e.g. 0.15 = 15%. NULL means "not yet verified" — the API must not guess.
    rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    effective_from: Mapped[date]
    effective_to: Mapped[date | None]
    source_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[UpdatedAt]
