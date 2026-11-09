"""Parsers against saved fixtures (real, trimmed payloads) — never live sites."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from bachatcheck.config import REPO_ROOT
from ingestion.providers.base import RawPayload
from ingestion.providers.frankfurter import FrankfurterProvider
from ingestion.providers.gold import GoldCsvProvider
from ingestion.providers.mufap import MufapProvider, slugify, split_category
from ingestion.providers.psx import PsxProvider
from ingestion.providers.sbp import SbpProvider
from ingestion.providers.tax_rules import TaxRulesProvider
from ingestion.records import (
    FundSnapshotRecord,
    FxRateRecord,
    MacroObservationRecord,
    PriceBarRecord,
    TaxRuleRecord,
)

Fixture = Callable[[str], bytes]


def payload(source: str, url: str, content: bytes) -> RawPayload:
    return RawPayload(source=source, url=url, content=content, content_type="x")


# --- SBP -------------------------------------------------------------------------------


def test_sbp_parses_cpi(fixture_bytes: Fixture) -> None:
    records = SbpProvider().parse(payload("sbp", "u", fixture_bytes("sbp_cpi_yoy.json")))
    assert len(records) == 4
    first = records[0]
    assert isinstance(first, MacroObservationRecord)
    assert first.series.code == "CPI_YOY"
    assert first.date == date(2026, 10, 31)
    assert first.value == Decimal("9.6")  # exact, from the string "9.6"
    assert first.status == "Normal"


def test_sbp_parses_tbill(fixture_bytes: Fixture) -> None:
    records = SbpProvider().parse(payload("sbp", "u", fixture_bytes("sbp_tbill_3m.json")))
    assert records
    assert {r.series.code for r in records if isinstance(r, MacroObservationRecord)} == {"TBILL_3M"}


def test_sbp_skips_missing_values(fixture_bytes: Fixture) -> None:
    # Real SBP rows with "" values and status "Missing value".
    assert SbpProvider().parse(payload("sbp", "u", fixture_bytes("sbp_missing_values.json"))) == []


def test_sbp_rejects_unexpected_shape() -> None:
    bad = b'{"columns": ["Foo"], "rows": []}'
    with pytest.raises(ValueError, match="missing columns"):
        SbpProvider().parse(payload("sbp", "u", bad))


# --- Frankfurter -----------------------------------------------------------------------


def test_frankfurter_parses_usd_pkr(fixture_bytes: Fixture) -> None:
    records = FrankfurterProvider().parse(
        payload("frankfurter", "u", fixture_bytes("frankfurter_usd_pkr.json"))
    )
    assert len(records) == 5
    first = records[0]
    assert isinstance(first, FxRateRecord)
    assert (first.base, first.quote, first.provider) == ("USD", "PKR", "frankfurter:SBP")
    assert first.date == date(2026, 9, 25)
    assert first.rate == Decimal("277.4714286")


# --- PSX -------------------------------------------------------------------------------


def test_psx_parses_kse100_as_index(fixture_bytes: Fixture) -> None:
    p = payload("psx", "psxdata://stocks/KSE100?start=x&end=y", fixture_bytes("psx_kse100.csv"))
    records = PsxProvider().parse(p)
    assert len(records) == 5
    first = records[0]
    assert isinstance(first, PriceBarRecord)
    assert first.instrument.kind == "index"
    assert first.instrument.symbol == "KSE100"
    assert first.date == date(2026, 11, 6)
    assert first.close == Decimal("173886.69")
    assert first.high == Decimal("174369.2")
    assert first.volume == 195810882
    assert all(r.validate(date(2026, 11, 10)) is None for r in records)


def test_psx_stock_symbol_is_a_stock() -> None:
    csv_bytes = (
        b"date,open,high,low,close,volume,is_anomaly\n2026-11-06,310,315,309,312.89,100,False\n"
    )
    [rec] = PsxProvider().parse(payload("psx", "psxdata://stocks/OGDC?start=a&end=b", csv_bytes))
    assert isinstance(rec, PriceBarRecord)
    assert rec.instrument.kind == "stock"
    assert rec.close == Decimal("312.89")


def test_psx_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        PsxProvider().parse(payload("psx", "psxdata://stocks/X?a", b"date,close\n2026-01-01,1\n"))


# --- MUFAP (synthetic workbook in MUFAP's real layout; real exports aren't committed) ---

HEADER = [
    "Sector", "Category", "Fund Name", "Rating", "Benchmark", "Validity Date", "NAV",
    "YTD", "MTD", "1 Day", "15 Days", "30 Days", "90 Days", "180 Days", "270 Days",
    "365 Days", "2 Years", "3 Years",
]  # fmt: skip


def mufap_workbook(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Performance Summary | MUTUAL FUNDS ASSOCIATION OF PAKISTAN"])
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def returns(*values: object) -> list[object]:
    return list(values) + ["N/A"] * (11 - len(values))


def test_mufap_parses_rows_and_derives_fields() -> None:
    content = mufap_workbook(
        [
            ["Open-End Funds", "Money Market (Annualized Return )", "Test Cash Fund", "AA+(f)",
             "N/A", "Nov 10, 2026", 10.6639, *returns(10.83, 10.79, 10.62)],
            ["Open-End Funds", "Shariah Compliant Equity (Absolute Return )", "Test Islamic Fund",
             None, 12, "Nov 06, 2026", 54.1507, *returns(-2.5)],
        ]
    )  # fmt: skip
    records = MufapProvider().parse(payload("mufap", "file://x.xlsx", content))
    assert len(records) == 2
    cash, islamic = records
    assert isinstance(cash, FundSnapshotRecord) and isinstance(islamic, FundSnapshotRecord)

    assert cash.instrument.symbol == "test-cash-fund"
    assert cash.instrument.category == "Money Market"
    assert cash.instrument.return_basis == "annualized"
    assert cash.instrument.is_shariah is False
    assert cash.instrument.rating == "AA+(f)"
    assert cash.as_of_date == date(2026, 11, 10)
    assert cash.nav == Decimal("10.6639")
    assert cash.returns["ret_ytd"] == Decimal("10.83")
    assert cash.returns["ret_3y"] is None  # "N/A"

    assert islamic.instrument.is_shariah is True
    assert islamic.instrument.return_basis == "absolute"
    assert islamic.instrument.rating is None
    assert islamic.returns["ret_ytd"] == Decimal("-2.5")


def test_mufap_skips_bad_rows_without_failing_the_file() -> None:
    content = mufap_workbook(
        [
            ["Open-End Funds", "Income (Annualized Return )", "No NAV Fund", "A", "N/A",
             "Nov 10, 2026", "N/A", *returns()],
            ["Open-End Funds", "Income (Annualized Return )", "Bad Date Fund", "A", "N/A",
             "sometime", 10, *returns()],
            ["Open-End Funds", "Income (Annualized Return )", "Good Fund", "A", "N/A",
             "Nov 10, 2026", 10, *returns()],
        ]
    )  # fmt: skip
    records = MufapProvider().parse(payload("mufap", "file://x.xlsx", content))
    assert [r.instrument.name for r in records if isinstance(r, FundSnapshotRecord)] == [
        "Good Fund"
    ]


def test_mufap_requires_header() -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["not", "a", "mufap", "file"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError, match="no header row"):
        MufapProvider().parse(payload("mufap", "file://x.xlsx", buf.getvalue()))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Money Market (Annualized Return )", ("Money Market", "annualized")),
        ("Equity (Absolute Return )", ("Equity", "absolute")),
        ("Fund of Funds", ("Fund of Funds", None)),
    ],
)
def test_split_category(raw: str, expected: tuple[str, str | None]) -> None:
    assert split_category(raw) == expected


def test_slugify() -> None:
    assert slugify("Alfalah Cash Fund - II") == "alfalah-cash-fund-ii"


# --- Gold & tax rules -------------------------------------------------------------------


def test_gold_csv() -> None:
    content = b'date,price_pkr,source_note\n2026-11-01,"412,500",test note\n2026-11-02,,blank\n'
    [rec] = GoldCsvProvider().parse(payload("gold", "file://g.csv", content))
    assert isinstance(rec, PriceBarRecord)
    assert rec.close == Decimal("412500")
    assert rec.instrument.kind == "gold"


def test_repo_gold_csv_has_expected_header() -> None:
    path: Path = REPO_ROOT / "data" / "gold" / "gold_pkr_per_tola_24k.csv"
    assert path.read_text().splitlines()[0] == "date,price_pkr,source_note"


def test_repo_tax_rules_are_unverified_placeholders() -> None:
    content = (REPO_ROOT / "data" / "tax_rules.yaml").read_bytes()
    records = TaxRulesProvider().parse(payload("tax_rules", "file://t.yaml", content))
    rules = [r for r in records if isinstance(r, TaxRuleRecord)]
    assert len(rules) >= 9
    # Until the owner fills in verified FBR rates, nothing may carry a guessed number.
    assert all(r.rate is None and not r.verified for r in rules)
    assert all(r.validate(date(2026, 11, 10)) is None for r in rules)


def test_tax_rule_rate_parses_from_string() -> None:
    content = b"""rules:
  - asset_class: stock
    tax_type: capital_gains
    rate: "0.15"
    effective_from: 2025-07-01
    verified: true
    source_url: https://example.test/fbr
"""
    [rule] = TaxRulesProvider().parse(payload("tax_rules", "file://t.yaml", content))
    assert isinstance(rule, TaxRuleRecord)
    assert rule.rate == Decimal("0.15")
    assert rule.effective_from == date(2025, 7, 1)
