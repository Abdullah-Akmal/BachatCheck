"""Series helpers with small, hand-checkable inputs."""

from datetime import date
from decimal import Decimal as D

from bachatcheck.returns.core import round_money, round_rate
from bachatcheck.returns.series import (
    accrual_path,
    add_months,
    compound_path,
    cpi_index,
    deflate,
    inflation_between,
    month_ends,
    monthly_stepper,
    price_path,
    tenor_stepper,
    value_on_or_before,
)

PTS = [(date(2026, 1, 31), D(1)), (date(2026, 2, 28), D(2)), (date(2026, 3, 31), D(3))]


def test_value_on_or_before() -> None:
    assert value_on_or_before(PTS, date(2026, 2, 28)) == (date(2026, 2, 28), D(2))
    assert value_on_or_before(PTS, date(2026, 3, 15)) == (date(2026, 2, 28), D(2))
    assert value_on_or_before(PTS, date(2026, 1, 1)) is None


def test_add_months_clamps_day() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 10), 2) == date(2027, 1, 10)
    assert add_months(date(2026, 11, 10), -12) == date(2025, 11, 10)


def test_month_ends() -> None:
    assert month_ends(date(2026, 1, 15), date(2026, 4, 10)) == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]


def test_cpi_index_chains_monthly_changes() -> None:
    # +1% then +2%: 100 -> 101 -> 103.02
    idx = cpi_index([(date(2026, 1, 31), D(1)), (date(2026, 2, 28), D(2))])
    assert idx == [
        (date(2025, 12, 31), D(100)),
        (date(2026, 1, 31), D(101)),
        (date(2026, 2, 28), D("103.02")),
    ]
    # Inflation Dec -> Feb = 103.02 / 100 - 1 = 3.02%, not 1% + 2%.
    assert inflation_between(idx, date(2026, 1, 10), date(2026, 3, 5)) == D("0.0302")
    assert inflation_between(idx, date(2025, 6, 1), date(2026, 3, 5)) is None


def test_price_path_buys_at_start_price() -> None:
    prices = [(date(2026, 1, 2), D(100)), (date(2026, 2, 27), D(110)), (date(2026, 3, 6), D(120))]
    result = price_path(D(1000), prices, date(2026, 1, 5), date(2026, 3, 10))
    assert result is not None
    path, last = result
    assert last == date(2026, 3, 6)
    assert path[0] == (date(2026, 1, 5), D(1000))
    # Jan 31 -> still 100; Feb 28 -> 110; Mar 10 -> 120
    assert [v for _, v in path[1:]] == [D(1000), D(1100), D(1200)]


def test_price_path_none_without_start_price() -> None:
    assert price_path(D(1), [(date(2026, 2, 1), D(5))], date(2026, 1, 1), date(2026, 3, 1)) is None


def test_tbill_rolls_compound_and_partial_period_is_pro_rata() -> None:
    # 12% for 91 days, then 10% for the last 9 days (100 days total).
    rates = [(date(2026, 1, 1), D(12)), (date(2026, 3, 15), D(10))]
    path = accrual_path(D(100_000), rates, date(2026, 1, 1), date(2026, 4, 11), tenor_stepper(91))
    assert path is not None
    # Roll 1: 100000 * (1 + 0.12 * 91/365) = 102991.7808...
    assert round_money(path[1][1]) == D("102991.78")
    assert path[1][0] == date(2026, 4, 2)
    # Partial: 102991.7808 * (1 + 0.10 * 9/365) = 103245.73...
    assert path[-1][0] == date(2026, 4, 11)
    assert round_money(path[-1][1]) == D("103245.73")


def test_accrual_withholds_tax_on_each_credit() -> None:
    rates = [(date(2026, 1, 1), D("12"))]
    # One 31-day month at 12%, 20% withheld:
    # profit = 1000 * 0.12 * 31/365 = 10.19178...; net = 8.15342...
    path = accrual_path(
        D(1000), rates, date(2026, 1, 1), date(2026, 2, 1), monthly_stepper, tax_rate=D("0.2")
    )
    assert path is not None
    assert round_money(path[-1][1]) == D("1008.15")


def test_accrual_none_without_rate_at_start() -> None:
    assert (
        accrual_path(
            D(1), [(date(2026, 5, 1), D(5))], date(2026, 1, 1), date(2026, 6, 1), monthly_stepper
        )
        is None
    )


def test_compound_path_hits_end_value() -> None:
    path = compound_path(D(1000), D("0.21"), date(2025, 1, 1), date(2027, 1, 1))
    assert path[0] == (date(2025, 1, 1), D(1000))
    assert round_money(path[-1][1]) == D("1210.00")
    # Halfway (730 days total, Dec 31 2025 is day 364) is ~ sqrt(1.21) = 1.1
    mid = dict(path)[date(2025, 12, 31)]
    assert D("1099") < mid < D("1100")


def test_deflate_uses_cpi() -> None:
    idx = cpi_index([(date(2026, 1, 31), D(10))])  # 100 -> 110
    out = deflate([(date(2026, 1, 1), D(1000)), (date(2026, 2, 1), D(1100))], idx, date(2026, 1, 1))
    assert [round_rate(v) for _, v in out] == [D("1000.000000"), D("1000.000000")]
