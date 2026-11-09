"""Compare engine on synthetic, hand-checkable inputs (no database)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from bachatcheck.repo import FundRow, TaxRuleRow
from bachatcheck.returns.compare import AssetResult, CompareInputs, CompareResult, run_compare
from bachatcheck.returns.series import month_ends

END = date(2026, 11, 10)
Q4 = D("0.0001")


def cpi_one_percent_a_month() -> list[tuple[date, D]]:
    # Month ends Oct 2025 .. Oct 2026, +1% each month.
    first = date(2025, 10, 31)
    return [(d, D(1)) for d in [first, *month_ends(first, date(2026, 11, 1))]]


def fund(
    name: str, category: str, ret_365d: str, basis: str = "annualized", shariah: bool = False
) -> FundRow:
    return FundRow(
        symbol=name.lower(),
        name=name,
        category=category,
        sector="Open-End Funds",
        amc=None,
        rating=None,
        is_shariah=shariah,
        return_basis=basis,
        as_of_date=date(2026, 11, 6),
        nav=D(10),
        returns={"ret_365d": D(ret_365d)},
    )


def stock_cgt(rate: str | None, verified: bool) -> TaxRuleRow:
    return TaxRuleRow(
        "stock",
        "capital_gains",
        "filer",
        D(rate) if rate else None,
        date(2025, 7, 1),
        None,
        None,
        None,
        verified,
    )


def inputs(**overrides: object) -> CompareInputs:
    base: dict[str, object] = {
        "cpi_mom": cpi_one_percent_a_month(),
        "savings_rates": [(date(2020, 1, 31), D("4.29"))],
        "savings_series_code": "DEPOSIT_RATE_FRESH",
        "tbill_rates": {"TBILL_3M": [(date(2025, 1, 1), D(12))]},
        "index_prices": {
            "KSE100": [(date(2025, 11, 7), D(100)), (date(2026, 11, 6), D(130))],
            "KMI30": [(date(2025, 11, 7), D(200)), (date(2026, 11, 6), D(250))],
        },
        "usd_pkr": [(date(2025, 11, 7), D(280)), (date(2026, 10, 30), D(277))],
        "gold": [],
        "funds": [
            fund("A", "Money Market", "10"),
            fund("B", "Money Market", "12"),
            fund("C", "Money Market", "11"),
            fund("E", "Equity", "30", basis="absolute"),
            fund("S", "Shariah Compliant Equity", "25", basis="absolute", shariah=True),
        ],
        "funds_demo": False,
        "tax_rules": [stock_cgt("0.15", verified=True)],
    }
    base.update(overrides)
    return CompareInputs(**base)  # type: ignore[arg-type]


def by_key(result: CompareResult, key: str) -> AssetResult:
    return next(a for a in result.assets if a.key == key)


def test_inflation_compounds_monthly() -> None:
    r = run_compare(inputs(), D(100_000), 1, END)
    assert r.start == date(2025, 11, 10)
    # Oct-2025 -> Oct-2026 = 12 months of +1%: 1.01^12 - 1 = 0.126825...
    assert r.inflation is not None and r.inflation.quantize(D("0.000001")) == D("0.126825")
    assert r.cpi_as_of == date(2026, 10, 31)


def test_index_nominal_real_and_post_tax() -> None:
    kse = by_key(run_compare(inputs(), D(100_000), 1, END), "kse100")
    assert kse.available
    assert kse.end_value == D(130_000)
    assert kse.nominal_return == D("0.3")
    # Real: 1.30 / 1.126825 - 1 = 0.153684...
    assert kse.real_return is not None and kse.real_return.quantize(Q4) == D("0.1537")
    # Post-tax at a verified 15% CGT: 0.30 * 0.85 = 0.255
    assert kse.tax is not None and kse.tax.status == "applied"
    assert kse.post_tax_return == D("0.255")
    assert kse.post_tax_end_value == D(125_500)


def test_unverified_tax_gives_no_post_tax_numbers() -> None:
    r = run_compare(inputs(tax_rules=[stock_cgt(None, verified=False)]), D(100_000), 1, END)
    kse = by_key(r, "kse100")
    assert kse.tax is not None and kse.tax.status == "unverified"
    assert kse.post_tax_return is None and kse.post_tax_end_value is None
    assert kse.nominal_return == D("0.3")  # pre-tax numbers still there


def test_usd_holding_loses_when_rupee_strengthens() -> None:
    usd = by_key(run_compare(inputs(), D(280_000), 1, END), "usd")
    # 280,000 PKR -> 1,000 USD -> 277,000 PKR
    assert usd.end_value == D(277_000)
    assert usd.data_as_of == date(2026, 10, 30)


def test_fund_category_uses_median_trailing_return() -> None:
    mm = by_key(run_compare(inputs(), D(100_000), 1, END), "fund:money_market")
    # median(10, 11, 12) = 11% -> 111,000
    assert mm.available and mm.path_kind == "interpolated"
    assert mm.end_value is not None and mm.end_value.quantize(D("0.01")) == D("111000.00")


def test_funds_unavailable_beyond_three_years() -> None:
    r = run_compare(inputs(), D(100_000), 5, END)
    mm = by_key(r, "fund:money_market")
    assert not mm.available and "3 years" in (mm.reason or "")


def test_savings_override_rate_and_default_note() -> None:
    r = run_compare(inputs(), D(100_000), 1, END, savings_rate_override_pct=D(12))
    sav = by_key(r, "savings")
    assert sav.available
    # 12 monthly credits at 12% simple-per-month compound to a bit over 12.6%:
    # e.g. (1 + 0.12/12)^12 - 1 = 0.126825; actual/365 day counts land within a few bp of it.
    assert sav.nominal_return is not None and D("0.1260") < sav.nominal_return < D("0.1275")
    assert "your rate" in sav.notes[0]


def test_shariah_mode_swaps_index_and_excludes_interest_assets() -> None:
    r = run_compare(inputs(), D(100_000), 1, END, shariah_only=True)
    keys = {a.key: a for a in r.assets}
    assert not keys["savings"].available and not keys["tbill_3m"].available
    assert "kse100" not in keys and keys["kmi30"].end_value == D(125_000)
    assert "fund:shariah_compliant_equity" in keys and "fund:equity" not in keys


def test_missing_data_is_reported_not_faked() -> None:
    r = run_compare(inputs(), D(100_000), 1, END)
    gold = by_key(r, "gold")
    assert not gold.available and "by hand" in (gold.reason or "")
    tbill_6m = by_key(r, "tbill_6m")  # no TBILL_6M data supplied
    assert not tbill_6m.available


def test_input_validation() -> None:
    with pytest.raises(ValueError):
        run_compare(inputs(), D(0), 1, END)
    with pytest.raises(ValueError):
        run_compare(inputs(), D(1000), 0, END)
