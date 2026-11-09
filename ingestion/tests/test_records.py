from datetime import date
from decimal import Decimal

import pytest

from ingestion.records import (
    FundSnapshotRecord,
    FxRateRecord,
    InstrumentRef,
    PriceBarRecord,
    TaxRuleRecord,
    to_decimal,
)

TODAY = date(2026, 11, 10)
STOCK = InstrumentRef(kind="stock", symbol="TEST", name="Test", source="t")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (10.83, Decimal("10.83")),  # float goes through repr, not binary expansion
        (0.1, Decimal("0.1")),
        ("1,250,000", Decimal("1250000")),
        (" 277.4714286 ", Decimal("277.4714286")),
        (42, Decimal(42)),
        ("N/A", None),
        ("", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_to_decimal(raw: object, expected: Decimal | None) -> None:
    assert to_decimal(raw) == expected


def test_to_decimal_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        to_decimal("twelve")


def bar(**kw: object) -> PriceBarRecord:
    base: dict[str, object] = {
        "instrument": STOCK,
        "date": date(2026, 11, 6),
        "open": Decimal(100),
        "high": Decimal(110),
        "low": Decimal(95),
        "close": Decimal(105),
        "volume": 1000,
        "source": "t",
    }
    base.update(kw)
    return PriceBarRecord(**base)  # type: ignore[arg-type]


def test_valid_bar_passes() -> None:
    assert bar().validate(TODAY) is None


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"date": date(2026, 11, 11)}, "future"),
        ({"low": Decimal(120)}, "low"),
        ({"close": Decimal(120)}, "close"),
        ({"open": Decimal(90)}, "open"),
        ({"close": Decimal(0)}, "non-positive"),
        ({"volume": -1}, "negative volume"),
    ],
)
def test_bad_bars_are_rejected(override: dict[str, object], fragment: str) -> None:
    problem = bar(**override).validate(TODAY)
    assert problem is not None and fragment in problem


def test_close_only_bar_is_valid() -> None:
    # Gold rows have only a close.
    assert bar(open=None, high=None, low=None, volume=None).validate(TODAY) is None


def test_fund_snapshot_checks_nav_and_return_bounds() -> None:
    fund = InstrumentRef(kind="mutual_fund", symbol="f", name="F", source="t")
    ok = FundSnapshotRecord(fund, TODAY, Decimal("10.66"), "t", {"ret_365d": Decimal("10.72")})
    assert ok.validate(TODAY) is None
    assert "NAV" in (FundSnapshotRecord(fund, TODAY, Decimal(0), "t").validate(TODAY) or "")
    wild = FundSnapshotRecord(fund, TODAY, Decimal(10), "t", {"ret_ytd": Decimal(5000)})
    assert "sanity" in (wild.validate(TODAY) or "")


def test_fx_rate_must_be_positive() -> None:
    assert FxRateRecord("USD", "PKR", TODAY, Decimal("277.4"), "p").validate(TODAY) is None
    assert FxRateRecord("USD", "PKR", TODAY, Decimal(0), "p").validate(TODAY) is not None


def test_tax_rule_rate_is_a_fraction_and_verified_needs_a_rate() -> None:
    rule = TaxRuleRecord("stock", "capital_gains", "filer", date(2025, 7, 1), Decimal("0.15"))
    assert rule.validate(TODAY) is None
    assert TaxRuleRecord("stock", "cgt", "filer", date(2025, 7, 1), Decimal(15)).validate(TODAY)
    unverified_placeholder = TaxRuleRecord("stock", "cgt", "filer", date(2025, 7, 1), None)
    assert unverified_placeholder.validate(TODAY) is None
    bad = TaxRuleRecord("stock", "cgt", "filer", date(2025, 7, 1), None, verified=True)
    assert "verified" in (bad.validate(TODAY) or "")
