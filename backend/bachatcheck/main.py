"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bachatcheck import __version__
from bachatcheck.api.middleware import RateLimitMiddleware, TTLCacheMiddleware
from bachatcheck.api.v1 import router as v1_router
from bachatcheck.config import Settings, get_settings
from bachatcheck.log_config import configure_logging

CACHED_PREFIXES = (
    "/api/v1/compare",
    "/api/v1/funds",
    "/api/v1/stocks",
    "/api/v1/macro",
    "/api/v1/tax-rules",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="BachatCheck API",
        version=__version__,
        description="Compare Pakistani savings options by real (after inflation and tax) return. "
        "For education only. Not investment advice.",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    # Starlette runs the last-added middleware first: CORS -> rate limit -> cache -> app.
    app.add_middleware(TTLCacheMiddleware, ttl=settings.cache_ttl_seconds, prefixes=CACHED_PREFIXES)
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=settings.rate_limit_per_minute,
        trust_forwarded_for=settings.trust_forwarded_for,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(v1_router)
    return app


app = create_app()
