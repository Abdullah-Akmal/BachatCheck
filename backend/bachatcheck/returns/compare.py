"""The compare engine: how `amount` would have grown in each asset class over `years`.

Each asset produces a nominal PKR path. Real values deflate that path by CPI (an index chained
from SBP's month-on-month national CPI). Post-tax figures appear only when a *verified* tax
rule exists for the asset; otherwise the API says the tax assumption is unverified.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from bachatcheck.repo import FundRow, TaxRuleRow, active_tax_rate
from bachatcheck.returns.core import (
    ONE,
    absolute_return,
    annualized_to_total,
    cagr,
    pct_to_fraction,
    post_tax_return,
    real_return,
)
from bachatcheck.returns.series import (
    Path,
    Point,
    accrual_path,
    add_months,
    compound_path,
    cpi_index,
    inflation_between,
    month_ends,
    monthly_stepper,
    price_path,
    tenor_stepper,
    value_on_or_before,
)

FUND_HORIZON_FIELD = {1: "ret_365d", 2: "ret_2y", 3: "ret_3y"}
CONVENTIONAL_FUND_CATEGORIES = ("Money Market", "Income", "Equity")
SHARIAH_FUND_CATEGORIES = (
    "Shariah Compliant Money Market",
    "Shariah Compliant Income",
    "Shariah Compliant Equity",
)
TBILL_TENORS = (
    ("TBILL_3M", 91, "3 months"),
    ("TBILL_6M", 182, "6 months"),
    ("TBILL_12M", 364, "12 months"),
)


@dataclass
class CompareInputs:
    """Everything the engine needs, already loaded. Keeps the engine free of I/O."""

    cpi_mom: list[Point]
    savings_rates: list[Point]
    savings_series_code: str
    tbill_rates: dict[str, list[Point]]
    index_prices: dict[str, list[Point]]  # "KSE100", "KMI30"
    usd_pkr: list[Point]
    gold: list[Point]
    funds: list[FundRow]
    funds_demo: bool
    tax_rules: list[TaxRuleRow]


@dataclass
class TaxOutcome:
    status: str  # "applied" | "unverified" | "not_applicable"
    asset_class: str
    tax_type: str
    rate: Decimal | None = None
    source_url: str | None = None


@dataclass
class AssetResult:
    key: str
    label: str
    group: str
    available: bool
    reason: str | None = None
    notes: list[str] = field(default_factory=list)
    data_as_of: date | None = None
    demo: bool = False
    path_kind: str = "actual"  # "actual" | "interpolated"
    path: Path = field(default_factory=list)
    post_tax_path: Path | None = None
    tax: TaxOutcome | None = None
    # Filled by finalize():
    end_value: Decimal | None = None
    nominal_return: Decimal | None = None
    cagr: Decimal | None = None
    real_end_value: Decimal | None = None
    real_return: Decimal | None = None
    post_tax_end_value: Decimal | None = None
    post_tax_return: Decimal | None = None
    post_tax_real_return: Decimal | None = None


@dataclass
class CompareResult:
    amount: Decimal
    years: int
    start: date
    end: date
    shariah_only: bool
    filer_status: str
    inflation: Decimal | None
    inflation_cagr: Decimal | None
    cpi_as_of: date | None
    dates: list[date]
    inflation_series: list[Decimal | None]
    assets: list[AssetResult]


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def _unavailable(key: str, label: str, group: str, reason: str) -> AssetResult:
    return AssetResult(key=key, label=label, group=group, available=False, reason=reason)


class _Ctx:
    def __init__(self, inp: CompareInputs, amount: Decimal, start: date, end: date, filer: str):
        self.inp, self.amount, self.start, self.end, self.filer = inp, amount, start, end, filer

    def tax(self, asset_class: str, tax_type: str) -> TaxOutcome:
        rule = active_tax_rate(self.inp.tax_rules, asset_class, tax_type, self.filer, self.end)
        if rule is None or rule.rate is None or not rule.verified:
            return TaxOutcome("unverified", asset_class, tax_type)
        return TaxOutcome("applied", asset_class, tax_type, rule.rate, rule.source_url)


def _accrual_asset(
    c: _Ctx,
    key: str,
    label: str,
    group: str,
    rates: list[Point],
    stepper: Callable[[date], date],
    tax_class: str,
) -> AssetResult:
    path = accrual_path(c.amount, rates, c.start, c.end, stepper)
    if path is None:
        first = rates[0][0].isoformat() if rates else "n/a"
        return _unavailable(
            key, label, group, f"No rate data before the start date (data from {first})."
        )
    tax = c.tax(tax_class, "withholding_on_profit")
    post = (
        accrual_path(c.amount, rates, c.start, c.end, stepper, tax_rate=tax.rate)
        if tax.rate is not None
        else None
    )
    last = value_on_or_before(rates, c.end)
    return AssetResult(
        key=key,
        label=label,
        group=group,
        available=True,
        path=path,
        post_tax_path=post,
        tax=tax,
        data_as_of=last[0] if last else None,
    )


def _price_asset(
    c: _Ctx, key: str, label: str, group: str, prices: list[Point], tax_class: str
) -> AssetResult:
    result = price_path(c.amount, prices, c.start, c.end)
    if result is None:
        first = prices[0][0].isoformat() if prices else "none yet"
        return _unavailable(
            key, label, group, f"No price data at the start date (data from {first})."
        )
    path, last = result
    return AssetResult(
        key=key,
        label=label,
        group=group,
        available=True,
        path=path,
        tax=c.tax(tax_class, "capital_gains"),
        data_as_of=last,
    )


def _usd_asset(c: _Ctx) -> AssetResult:
    # Buy dollars at the start, convert back at the end: value = amount * R(t) / R(start).
    result = price_path(c.amount, c.inp.usd_pkr, c.start, c.end)
    if result is None:
        return _unavailable("usd", "US dollars (cash)", "fx", "No USD/PKR rate at the start date.")
    path, last = result
    return AssetResult(
        key="usd",
        label="US dollars (cash)",
        group="fx",
        available=True,
        path=path,
        tax=c.tax("usd", "capital_gains"),
        data_as_of=last,
        notes=["Converted at SBP's average interbank rate; real exchange spreads are wider."],
    )


def _fund_asset(c: _Ctx, category: str, years: int) -> AssetResult:
    key = "fund:" + category.lower().replace(" ", "_")
    label = f"{category} funds (median)"
    field_name = FUND_HORIZON_FIELD.get(years)
    if field_name is None:
        return _unavailable(
            key, label, "fund", "MUFAP publishes trailing returns for up to 3 years only."
        )
    funds = [
        f for f in c.inp.funds if f.category == category and f.returns.get(field_name) is not None
    ]
    values = [v for f in funds if (v := f.returns.get(field_name)) is not None]
    if not values:
        return _unavailable(key, label, "fund", "No funds in this category report this horizon.")
    basis = funds[0].return_basis
    rate = pct_to_fraction(_median(values))
    total = annualized_to_total(rate, Decimal(years)) if basis == "annualized" else rate
    return AssetResult(
        key=key,
        label=label,
        group="fund",
        available=True,
        path=compound_path(c.amount, total, c.start, c.end),
        path_kind="interpolated",
        tax=c.tax("mutual_fund", "capital_gains"),
        data_as_of=max(f.as_of_date for f in funds),
        demo=c.inp.funds_demo,
        notes=[
            f"Median of {len(funds)} funds' trailing {years}-year return "
            f"({'annualized' if basis == 'annualized' else 'absolute'}, as reported by MUFAP).",
            "The chart line between start and end is illustrative; only the end value is data.",
        ],
    )


def _finalize(a: AssetResult, c: _Ctx, index: list[Point]) -> None:
    if not a.available or not a.path:
        return
    end_value = a.path[-1][1]
    days = (a.path[-1][0] - c.start).days or 1
    infl = inflation_between(index, c.start, a.path[-1][0])
    a.end_value = end_value
    a.nominal_return = absolute_return(c.amount, end_value)
    a.cagr = cagr(a.nominal_return, days)
    if infl is not None:
        a.real_return = real_return(a.nominal_return, infl)
        a.real_end_value = c.amount * (ONE + a.real_return)

    if a.tax is None or a.tax.status != "applied" or a.tax.rate is None:
        return
    if a.post_tax_path is not None:  # tax already withheld along the way
        a.post_tax_end_value = a.post_tax_path[-1][1]
        a.post_tax_return = absolute_return(c.amount, a.post_tax_end_value)
    else:  # tax on the gain at the end
        a.post_tax_return = post_tax_return(a.nominal_return, a.tax.rate)
        a.post_tax_end_value = c.amount * (ONE + a.post_tax_return)
    if infl is not None:
        a.post_tax_real_return = real_return(a.post_tax_return, infl)


def run_compare(
    inp: CompareInputs,
    amount: Decimal,
    years: int,
    end: date,
    shariah_only: bool = False,
    filer_status: str = "filer",
    savings_rate_override_pct: Decimal | None = None,
) -> CompareResult:
    if amount <= 0:
        raise ValueError("amount must be positive")
    if not 1 <= years <= 30:
        raise ValueError("years must be between 1 and 30")
    start = add_months(end, -12 * years)
    c = _Ctx(inp, amount, start, end, filer_status)
    index = cpi_index(inp.cpi_mom)
    assets: list[AssetResult] = []

    # Bank savings
    if shariah_only:
        assets.append(
            _unavailable(
                "savings",
                "Bank savings account",
                "savings",
                "Conventional savings accounts pay interest, so they're excluded in "
                "Shariah-compliant mode (no Islamic deposit-rate series is available yet).",
            )
        )
    else:
        if savings_rate_override_pct is not None:
            rates: list[Point] = [(date(1900, 1, 1), savings_rate_override_pct)]
            note = f"Using your rate of {savings_rate_override_pct}% a year, held constant."
        else:
            rates = inp.savings_rates
            note = (
                "SBP's weighted-average deposit rate. It includes zero-profit current accounts, "
                "so it understates what a typical savings account pays; enter your bank's rate "
                "for a better estimate."
            )
        a = _accrual_asset(
            c, "savings", "Bank savings account", "savings", rates, monthly_stepper, "bank_savings"
        )
        a.notes.append(note)
        a.notes.append("Profit credited monthly and reinvested.")
        assets.append(a)

    # T-bills, rolled over at each maturity at the latest auction cut-off yield.
    for code, days, tenor in TBILL_TENORS:
        key, label = f"tbill_{tenor.split()[0]}m", f"T-bills ({tenor}, rolled over)"
        if shariah_only:
            assets.append(
                _unavailable(
                    key, label, "tbill", "T-bills pay interest; excluded in Shariah-compliant mode."
                )
            )
            continue
        a = _accrual_asset(
            c, key, label, "tbill", inp.tbill_rates.get(code, []), tenor_stepper(days), "tbill"
        )
        a.notes.append("Reinvested at each maturity at the latest SBP auction cut-off yield.")
        assets.append(a)

    # Stock index
    idx_symbol, idx_label = (
        ("KMI30", "KMI-30 index (Shariah)") if shariah_only else ("KSE100", "KSE-100 index")
    )
    a = _price_asset(
        c, idx_symbol.lower(), idx_label, "equity", inp.index_prices.get(idx_symbol, []), "stock"
    )
    a.notes.append("Index level only: dividends aren't added, and you can't buy an index directly.")
    assets.append(a)

    assets.append(_usd_asset(c))

    gold = _price_asset(c, "gold", "Gold (24k, per tola)", "gold", inp.gold, "gold")
    if not gold.available:
        gold.reason = (
            "Gold prices are maintained by hand and haven't been entered for this period yet."
        )
    gold.notes.append("Manually updated.")
    assets.append(gold)

    for category in SHARIAH_FUND_CATEGORIES if shariah_only else CONVENTIONAL_FUND_CATEGORIES:
        assets.append(_fund_asset(c, category, years))

    for a in assets:
        _finalize(a, c, index)

    grid = [start, *month_ends(start, end), end]
    infl_total = inflation_between(index, start, end)
    cpi_first = value_on_or_before(index, start)
    cpi_last = value_on_or_before(index, end)
    infl_cagr: Decimal | None = None
    if infl_total is not None and cpi_first and cpi_last and cpi_last[0] > cpi_first[0]:
        infl_cagr = cagr(infl_total, (cpi_last[0] - cpi_first[0]).days)
    return CompareResult(
        amount=amount,
        years=years,
        start=start,
        end=end,
        shariah_only=shariah_only,
        filer_status=filer_status,
        inflation=infl_total,
        inflation_cagr=infl_cagr,
        cpi_as_of=cpi_last[0] if cpi_last else None,
        dates=grid,
        inflation_series=[
            amount * (ONE + i) if (i := inflation_between(index, start, d)) is not None else None
            for d in grid
        ],
        assets=assets,
    )


def on_grid(path: Path, grid: list[date]) -> list[Decimal | None]:
    """Sample a path onto the chart's date grid (last known value at or before each date)."""
    out: list[Decimal | None] = []
    for d in grid:
        p = value_on_or_before(path, d)
        out.append(p[1] if p else None)
    return out


def real_on_grid(
    path: Path, grid: list[date], cpi_mom: list[Point], start: date
) -> list[Decimal | None]:
    index = cpi_index(cpi_mom)
    out: list[Decimal | None] = []
    for d, v in zip(grid, on_grid(path, grid), strict=True):
        infl = inflation_between(index, start, d)
        out.append(v / (ONE + infl) if v is not None and infl is not None else None)
    return out
