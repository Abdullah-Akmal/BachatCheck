"""Time-series helpers: lookups, a CPI price index, and growth paths for each kind of asset.

A "path" is a list of (date, value) points in PKR, starting with (start, amount).
"""

from __future__ import annotations

import bisect
import calendar
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from decimal import Decimal, localcontext

from bachatcheck.returns.core import ONE, PRECISION, pct_to_fraction, simple_interest_factor

Point = tuple[date, Decimal]
Path = list[Point]


def value_on_or_before(points: Sequence[Point], when: date) -> Point | None:
    """Latest point at or before `when`. `points` must be sorted by date ascending."""
    i = bisect.bisect_right([d for d, _ in points], when)
    return points[i - 1] if i else None


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_ends(start: date, end: date) -> list[date]:
    """Month-end dates strictly after `start` and before `end`."""
    out: list[date] = []
    y, m = start.year, start.month
    while True:
        d = date(y, m, calendar.monthrange(y, m)[1])
        if d >= end:
            return out
        if d > start:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def cpi_index(mom_pct: Sequence[Point], base: Decimal = Decimal(100)) -> list[Point]:
    """Chain month-on-month CPI changes (percent) into a price index.

    index[i] = base * prod_{j<=i} (1 + mom_j / 100), dated at each month end. The month
    before the first observation is implicitly `base`, so we prepend that point too.
    """
    if not mom_pct:
        return []
    first = mom_pct[0][0]
    prev_month_end = first.replace(day=1) - timedelta(days=1)
    out: list[Point] = [(prev_month_end, base)]
    level = base
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for d, pct in mom_pct:
            level = level * (ONE + pct_to_fraction(pct))
            out.append((d, level))
    return out


def inflation_between(index: Sequence[Point], start: date, end: date) -> Decimal | None:
    """Cumulative inflation between the CPI months at/before `start` and at/before `end`."""
    a = value_on_or_before(index, start)
    b = value_on_or_before(index, end)
    if a is None or b is None:
        return None
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return b[1] / a[1] - ONE


def price_path(
    amount: Decimal, prices: Sequence[Point], start: date, end: date
) -> tuple[Path, date] | None:
    """Buy at the latest price on/before `start`, mark to market at each month end and at `end`.

    Returns the path and the date of the last price used, or None if there's no starting price.
    """
    p0 = value_on_or_before(prices, start)
    last = value_on_or_before(prices, end)
    if p0 is None or last is None or p0[1] <= 0:
        return None
    path: Path = [(start, amount)]
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for d in [*month_ends(start, end), end]:
            p = value_on_or_before(prices, d)
            if p is not None:
                path.append((d, amount * p[1] / p0[1]))
    return path, last[0]


def accrual_path(
    amount: Decimal,
    annual_rates_pct: Sequence[Point],
    start: date,
    end: date,
    next_reset: Callable[[date], date],
    tax_rate: Decimal = Decimal(0),
) -> Path | None:
    """Grow `amount` at a variable annual rate, compounding at each reset date.

    At each reset (a T-bill rolling over, or a savings account crediting monthly profit) the
    rate in force is the latest observation at/before that reset. Profit for the period is
    simple interest on actual/365, then `tax_rate` is withheld from the profit, and the net
    is reinvested. The final partial period accrues pro rata up to `end`.

    Returns None when there's no rate observation at/before `start`.
    """
    if value_on_or_before(annual_rates_pct, start) is None:
        return None
    path: Path = [(start, amount)]
    value = amount
    period_start = start
    with localcontext() as ctx:
        ctx.prec = PRECISION
        while period_start < end:
            period_end = min(next_reset(period_start), end)
            rate_pt = value_on_or_before(annual_rates_pct, period_start)
            assert rate_pt is not None  # guaranteed by the start check; rates only move forward
            factor = simple_interest_factor(
                pct_to_fraction(rate_pt[1]), (period_end - period_start).days
            )
            profit = value * (factor - ONE)
            if profit > 0:
                profit *= ONE - tax_rate
            value += profit
            path.append((period_end, value))
            period_start = period_end
    return path


def compound_path(amount: Decimal, total_return: Decimal, start: date, end: date) -> Path:
    """A smooth monthly path at a constant rate that reaches `amount * (1 + total_return)` at `end`.

    Used for mutual funds, where MUFAP gives a trailing return but no NAV history yet. The
    in-between points are illustrative; only the end value comes from data.
    """
    total_days = (end - start).days
    growth = ONE + total_return
    path: Path = [(start, amount)]
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for d in [*month_ends(start, end), end]:
            frac = Decimal((d - start).days) / Decimal(total_days)
            path.append((d, amount * growth**frac if growth > 0 else amount * growth))
    return path


def deflate(path: Sequence[Point], index: Sequence[Point], start: date) -> Path:
    """Express each nominal value in start-date rupees using the CPI index."""
    out: Path = []
    with localcontext() as ctx:
        ctx.prec = PRECISION
        for d, v in path:
            infl = inflation_between(index, start, d)
            out.append((d, v / (ONE + infl) if infl is not None else v))
    return out


def tenor_stepper(days: int) -> Callable[[date], date]:
    return lambda d: d + timedelta(days=days)


def monthly_stepper(d: date) -> date:
    return add_months(d, 1)
