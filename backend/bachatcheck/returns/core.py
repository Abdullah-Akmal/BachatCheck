"""Core return formulas. Pure functions on Decimal, no I/O.

Conventions
-----------
* Returns and rates are **fractions**: Decimal("0.12") means 12%.
* Day count is actual/365, which is what Pakistan's money markets use.
* Computation runs at 34 significant digits; callers round only for display.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext

ZERO = Decimal(0)
ONE = Decimal(1)
DAYS_PER_YEAR = Decimal(365)
PRECISION = 34

MONEY_QUANTUM = Decimal("0.01")
RATE_QUANTUM = Decimal("0.000001")


def pct_to_fraction(pct: Decimal) -> Decimal:
    """12.5 (percent) -> 0.125."""
    return pct / Decimal(100)


def absolute_return(start_value: Decimal, end_value: Decimal) -> Decimal:
    """Total return over the period: end / start - 1."""
    if start_value <= 0:
        raise ValueError("start_value must be positive")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return end_value / start_value - ONE


def cagr(total_return: Decimal, days: int) -> Decimal:
    """Compound annual growth rate: (1 + total)^(365 / days) - 1.

    A total loss (total_return <= -1) has no meaningful CAGR and returns -1.
    """
    if days <= 0:
        raise ValueError("days must be positive")
    growth = ONE + total_return
    if growth <= 0:
        return -ONE
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return growth ** (DAYS_PER_YEAR / Decimal(days)) - ONE


def real_return(nominal: Decimal, inflation: Decimal) -> Decimal:
    """Fisher equation, exact form: (1 + nominal) / (1 + inflation) - 1."""
    if inflation <= -ONE:
        raise ValueError("inflation must be greater than -100%")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return (ONE + nominal) / (ONE + inflation) - ONE


def post_tax_return(nominal: Decimal, tax_rate: Decimal) -> Decimal:
    """Return after tax on gains: gains are taxed at `tax_rate`; losses are not refunded.

    A simplification: Pakistan's real rules differ by holding period, filer status and
    instrument. The rate itself always comes from the versioned tax_rules table.
    """
    if not ZERO <= tax_rate <= ONE:
        raise ValueError("tax_rate must be a fraction between 0 and 1")
    if nominal <= 0:
        return nominal
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return nominal * (ONE - tax_rate)


def simple_interest_factor(annual_rate: Decimal, days: int) -> Decimal:
    """Growth factor for `days` at a simple annual rate (actual/365): 1 + r * days / 365."""
    if days < 0:
        raise ValueError("days must be non-negative")
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return ONE + annual_rate * Decimal(days) / DAYS_PER_YEAR


def annualized_to_total(annual_rate: Decimal, years: Decimal) -> Decimal:
    """Total return from a compound annual rate held for `years`: (1 + r)^years - 1."""
    if annual_rate <= -ONE:
        return -ONE
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return (ONE + annual_rate) ** years - ONE


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def round_rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN)
