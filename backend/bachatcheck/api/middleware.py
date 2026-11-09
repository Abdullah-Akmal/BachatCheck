"""Small ASGI middlewares: per-IP rate limiting and an in-process TTL cache for heavy GETs.

Both are deliberately simple and in-memory: the API runs as a single small instance on a
free tier. With several instances you'd move both to Redis (or the CDN, for the cache).
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from collections.abc import Callable

from starlette.types import ASGIApp, Message, Receive, Scope, Send


def _client_ip(scope: Scope, trust_forwarded_for: bool) -> str:
    if trust_forwarded_for:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                return str(value.decode("latin-1").split(",")[0].strip())
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


class RateLimitMiddleware:
    """Fixed one-minute window per client IP. Returns 429 with Retry-After when exceeded."""

    def __init__(
        self,
        app: ASGIApp,
        per_minute: int,
        prefix: str = "/api/",
        exempt: tuple[str, ...] = ("/api/v1/health",),
        trust_forwarded_for: bool = False,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app, self.per_minute, self.prefix, self.exempt = app, per_minute, prefix, exempt
        self.trust_forwarded_for, self.clock = trust_forwarded_for, clock
        self.windows: dict[str, tuple[int, int]] = {}  # ip -> (window, count)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith(self.prefix) or path in self.exempt:
            await self.app(scope, receive, send)
            return

        now = self.clock()
        window = int(now // 60)
        ip = _client_ip(scope, self.trust_forwarded_for)
        w, count = self.windows.get(ip, (window, 0))
        count = count + 1 if w == window else 1
        self.windows[ip] = (window, count)
        if len(self.windows) > 10_000:  # drop stale windows
            self.windows = {k: v for k, v in self.windows.items() if v[0] == window}

        remaining = max(self.per_minute - count, 0)
        if count > self.per_minute:
            retry_after = str(60 - int(now % 60))
            body = json.dumps({"detail": "Too many requests. Please slow down."}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", retry_after.encode()),
                        (b"x-ratelimit-limit", str(self.per_minute).encode()),
                        (b"x-ratelimit-remaining", b"0"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(self.per_minute).encode()))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class TTLCacheMiddleware:
    """Caches successful GET responses for `ttl` seconds, keyed by path + sorted query string."""

    def __init__(
        self,
        app: ASGIApp,
        ttl: int,
        prefixes: tuple[str, ...],
        max_entries: int = 512,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app, self.ttl, self.prefixes, self.max_entries, self.clock = (
            app,
            ttl,
            prefixes,
            max_entries,
            clock,
        )
        self.store: OrderedDict[str, tuple[float, int, list[tuple[bytes, bytes]], bytes]] = (
            OrderedDict()
        )

    def _key(self, scope: Scope) -> str:
        query = scope.get("query_string", b"").decode("latin-1")
        return str(scope["path"]) + "?" + "&".join(sorted(p for p in query.split("&") if p))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            self.ttl <= 0
            or scope["type"] != "http"
            or scope.get("method") != "GET"
            or not scope.get("path", "").startswith(self.prefixes)
        ):
            await self.app(scope, receive, send)
            return

        key = self._key(scope)
        now = self.clock()
        hit = self.store.get(key)
        if hit and hit[0] > now:
            self.store.move_to_end(key)
            _, status, headers, body = hit
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [*headers, (b"x-cache", b"HIT")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        captured: dict[str, object] = {}
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0] != b"cache-control"]
                if message["status"] == 200:
                    headers.append((b"cache-control", f"public, max-age={self.ttl}".encode()))
                message["headers"] = [*headers, (b"x-cache", b"MISS")]
                captured["status"], captured["headers"] = message["status"], headers
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
                if not message.get("more_body") and captured.get("status") == 200:
                    self.store[key] = (
                        now + self.ttl,
                        200,
                        captured["headers"],  # type: ignore[assignment]
                        b"".join(chunks),
                    )
                    self.store.move_to_end(key)
                    while len(self.store) > self.max_entries:
                        self.store.popitem(last=False)
            await send(message)

        await self.app(scope, receive, capture)
