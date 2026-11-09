"""Rate limiting and response caching, on a tiny app with a fake clock (no database)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bachatcheck.api.middleware import RateLimitMiddleware, TTLCacheMiddleware


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_app(clock: FakeClock, per_minute: int = 3, ttl: int = 0) -> tuple[FastAPI, list[int]]:
    app = FastAPI()
    calls: list[int] = []

    @app.get("/api/v1/thing")
    def thing(x: int = 0) -> dict[str, int]:
        calls.append(x)
        return {"x": x, "calls": len(calls)}

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(TTLCacheMiddleware, ttl=ttl, prefixes=("/api/v1/thing",), clock=clock)
    app.add_middleware(RateLimitMiddleware, per_minute=per_minute, clock=clock)
    return app, calls


def test_rate_limit_blocks_then_resets_next_minute() -> None:
    clock = FakeClock()
    client = TestClient(make_app(clock)[0])
    statuses = [client.get("/api/v1/thing").status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    blocked = client.get("/api/v1/thing")
    assert blocked.headers["retry-after"] and blocked.json()["detail"].startswith("Too many")
    # Health is exempt.
    assert client.get("/api/v1/health").status_code == 200
    clock.now += 60
    ok = client.get("/api/v1/thing")
    assert ok.status_code == 200 and ok.headers["x-ratelimit-remaining"] == "2"


def test_cache_serves_hits_until_ttl_expires() -> None:
    clock = FakeClock()
    app, calls = make_app(clock, per_minute=100, ttl=60)
    client = TestClient(app)

    first = client.get("/api/v1/thing", params={"x": 1})
    again = client.get("/api/v1/thing?x=1")
    assert first.headers["x-cache"] == "MISS" and again.headers["x-cache"] == "HIT"
    assert again.json() == first.json() and calls == [1]
    assert "max-age=60" in first.headers["cache-control"]

    client.get("/api/v1/thing", params={"x": 2})  # different query -> separate entry
    assert calls == [1, 2]

    clock.now += 61
    assert client.get("/api/v1/thing?x=1").headers["x-cache"] == "MISS"
    assert calls == [1, 2, 1]


def test_cache_ignores_errors() -> None:
    clock = FakeClock()
    app, _ = make_app(clock, per_minute=100, ttl=60)
    client = TestClient(app)
    assert client.get("/api/v1/thing", params={"x": "bad"}).status_code == 422
    assert client.get("/api/v1/thing", params={"x": "bad"}).headers["x-cache"] == "MISS"
