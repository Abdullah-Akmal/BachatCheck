"""API endpoints against a seeded Postgres (see conftest.seed)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

END = "2026-11-10"


def asset(body: dict, key: str) -> dict:  # type: ignore[type-arg]
    return next(a for a in body["assets"] if a["key"] == key)


def test_compare_kse100_matches_hand_calculation(client: TestClient) -> None:
    r = client.get("/api/v1/compare", params={"amount": 100000, "years": 1, "end": END})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["start"] == "2025-11-10"
    # 12 months of +1% CPI: 1.01^12 - 1
    assert body["headline"]["inflation"] == "0.126825"
    assert body["headline"]["amount_needed_to_keep_up"] == "112682.50"

    kse = asset(body, "kse100")
    assert kse["end_value"] == "130000.00"  # money: 2 dp strings
    assert kse["nominal_return"] == "0.300000"
    assert kse["real_return"] == "0.153684"  # 1.30 / 1.126825 - 1
    assert kse["tax"]["status"] == "applied"
    assert kse["post_tax_return"] == "0.255000"
    assert len(kse["nominal_series"]) == len(body["dates"]) == len(kse["real_series"])
    assert "kse100" in body["headline"]["beat_inflation"]


def test_compare_reports_missing_data_and_unverified_tax(client: TestClient) -> None:
    body = client.get("/api/v1/compare", params={"amount": 50000, "years": 1, "end": END}).json()
    assert asset(body, "gold")["available"] is False
    assert asset(body, "tbill_6m")["available"] is False
    savings = asset(body, "savings")
    assert savings["available"] and savings["tax"]["status"] == "unverified"
    assert savings["post_tax_return"] is None
    # A 4.29% deposit rate loses to ~12.7% inflation.
    assert "savings" in body["headline"]["lost_to_inflation"]


def test_compare_savings_override_and_shariah(client: TestClient) -> None:
    body = client.get(
        "/api/v1/compare", params={"amount": 100000, "years": 1, "end": END, "savings_rate": 20}
    ).json()
    assert float(asset(body, "savings")["nominal_return"]) > 0.2
    shariah = client.get("/api/v1/compare", params={"years": 1, "end": END, "shariah": True}).json()
    assert asset(shariah, "savings")["available"] is False
    assert all(a["key"] != "kse100" for a in shariah["assets"])


def test_compare_validates_input(client: TestClient) -> None:
    assert client.get("/api/v1/compare", params={"amount": -5}).status_code == 422
    assert client.get("/api/v1/compare", params={"years": 11}).status_code == 422
    assert client.get("/api/v1/compare", params={"end": "2999-01-01"}).status_code == 422


def test_funds_real_mode(client: TestClient) -> None:
    body = client.get("/api/v1/funds").json()
    assert body["meta"]["data_mode"] == "real"
    assert body["total"] == 1
    fund = body["funds"][0]
    assert fund["nav"] == "10.663900" and fund["ret_365d"] == "10.720000"
    assert fund["as_of_date"] == "2026-11-09"

    detail = client.get("/api/v1/funds/test-cash-fund").json()
    assert [p[0] for p in detail["nav_history"]] == ["2026-11-08", "2026-11-09"]
    assert client.get("/api/v1/funds/nope").status_code == 404


def test_funds_demo_mode_serves_labelled_synthetic_data(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(funds_data_mode="demo")
    body = client.get(
        "/api/v1/funds", params={"shariah": True, "sort": "ret_365d", "order": "desc"}
    ).json()
    assert body["meta"]["data_mode"] == "demo"
    assert all(f["is_shariah"] for f in body["funds"]) and body["total"] > 0
    assert all(f["name"].startswith("Demo ") for f in body["funds"])
    returns = [float(f["ret_365d"]) for f in body["funds"]]
    assert returns == sorted(returns, reverse=True)

    compare = client.get("/api/v1/compare", params={"years": 1, "end": END}).json()
    assert asset(compare, "fund:money_market")["demo"] is True


def test_fund_categories(client: TestClient) -> None:
    cats = client.get("/api/v1/funds/categories").json()
    assert cats == [
        {"category": "Money Market", "is_shariah": False, "return_basis": "annualized", "count": 1}
    ]


def test_stock_lookup_vs_benchmark(client: TestClient) -> None:
    assert [
        i["symbol"] for i in client.get("/api/v1/stocks/search", params={"q": "og"}).json()
    ] == ["OGDC"]
    body = client.get("/api/v1/stocks/ogdc", params={"period": "1y"}).json()
    assert body["performance"]["total_return"] == "0.100000"  # 200 -> 220
    assert body["benchmark"]["total_return"] == "0.300000"  # 100 -> 130
    assert body["rebased"][0][1:] == ["100.000000", "100.000000"]
    assert body["partial"] is False  # seed data starts 2025-11-07, the window 2025-11-06
    assert client.get("/api/v1/stocks/ogdc", params={"period": "5y"}).json()["partial"] is True
    assert client.get("/api/v1/stocks/NOPE").status_code == 404


def test_stocks_disabled_in_demo_mode(make_client: Callable[..., TestClient]) -> None:
    assert (
        make_client(stocks_data_mode="demo")
        .get("/api/v1/stocks/search", params={"q": "o"})
        .status_code
        == 503
    )


def test_macro_freshness_tax_and_config(client: TestClient) -> None:
    codes = [s["code"] for s in client.get("/api/v1/macro").json()]
    assert codes == ["CPI_MOM", "DEPOSIT_RATE_FRESH", "TBILL_3M"]
    tb = client.get("/api/v1/macro/tbill_3m").json()
    assert tb["points"] == [["2024-01-01", "12.00000000"]]
    assert client.get("/api/v1/macro/NOPE").status_code == 404

    fresh = client.get("/api/v1/freshness").json()
    assert (
        fresh["sources"][0]["source"] == "sbp" and fresh["sources"][0]["last_status"] == "success"
    )
    assert fresh["data_as_of"]["prices:index"] == "2026-11-06"

    rules = client.get("/api/v1/tax-rules").json()
    assert rules[0]["rate"] == "0.150000" and rules[0]["verified"] is True
    assert client.get("/api/v1/config").json()["funds_data_mode"] == "real"
