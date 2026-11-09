"""Hand-calculated expected values for the core formulas (worked in comments)."""

from decimal import Decimal as D

import pytest

from bachatcheck.returns.core import (
    absolute_return,
    annualized_to_total,
    cagr,
    pct_to_fraction,
    post_tax_return,
    real_return,
    round_money,
    round_rate,
    simple_interest_factor,
)


def test_absolute_return() -> None:
    # 100,000 -> 125,000 : 125000/100000 - 1 = 0.25
    assert absolute_return(D(100_000), D(125_000)) == D("0.25")
    # 100 -> 80 : -0.2
    assert absolute_return(D(100), D(80)) == D("-0.2")


def test_absolute_return_rejects_non_positive_start() -> None:
    with pytest.raises(ValueError):
        absolute_return(D(0), D(10))


def test_cagr_two_years() -> None:
    # 21% over 730 days: (1.21)^(365/730) - 1 = sqrt(1.21) - 1 = 1.1 - 1 = 0.10
    assert round_rate(cagr(D("0.21"), 730)) == D("0.100000")


def test_cagr_one_year_is_identity() -> None:
    assert round_rate(cagr(D("0.0972"), 365)) == D("0.097200")


def test_cagr_half_year() -> None:
    # 5% over 182.5 days would be (1.05)^2 - 1 = 0.1025; use 146 days = 0.4 years:
    # (1.05)^(365/146) = 1.05^2.5 = 1.1297...  1.05^2 = 1.1025, sqrt(1.05)=1.024695077
    # 1.1025 * 1.024695077 = 1.129726322 -> 0.129726
    assert round_rate(cagr(D("0.05"), 146)) == D("0.129726")


def test_cagr_total_loss() -> None:
    assert cagr(D(-1), 365) == D(-1)


def test_real_return_fisher_exact() -> None:
    # nominal 12%, inflation 10%: 1.12 / 1.10 - 1 = 0.0181818...
    assert round_rate(real_return(D("0.12"), D("0.10"))) == D("0.018182")
    # Not the naive 12% - 10% = 2%.
    assert round_rate(real_return(D("0.12"), D("0.10"))) != D("0.02")


def test_real_return_negative_when_inflation_wins() -> None:
    # nominal 5%, inflation 9.6%: 1.05 / 1.096 - 1 = -0.0419708...
    assert round_rate(real_return(D("0.05"), D("0.096"))) == D("-0.041971")


def test_post_tax_return() -> None:
    # 12% gain, 15% tax: 0.12 * 0.85 = 0.102
    assert post_tax_return(D("0.12"), D("0.15")) == D("0.1020")
    # Losses aren't taxed (or refunded).
    assert post_tax_return(D("-0.05"), D("0.15")) == D("-0.05")
    with pytest.raises(ValueError):
        post_tax_return(D("0.1"), D(15))  # 15 is a percent, not a fraction


def test_simple_interest_factor_tbill() -> None:
    # 3-month bill: 91 days at 12%: 1 + 0.12 * 91 / 365 = 1.029917808...
    assert round_rate(simple_interest_factor(D("0.12"), 91)) == D("1.029918")


def test_annualized_to_total() -> None:
    # 10% a year for 3 years: 1.1^3 - 1 = 0.331
    assert annualized_to_total(D("0.10"), D(3)) == D("0.331")


def test_rounding_is_bankers() -> None:
    assert round_money(D("1250000.005")) == D("1250000.00")
    assert round_money(D("1250000.015")) == D("1250000.02")
    assert pct_to_fraction(D("9.6")) == D("0.096")
