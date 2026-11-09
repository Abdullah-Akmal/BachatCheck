"""Polite HTTP: a project User-Agent, timeouts, and retries with exponential backoff."""

from __future__ import annotations

from collections.abc import Mapping

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from bachatcheck.config import get_settings

log = structlog.get_logger()

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": get_settings().http_user_agent},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def get(client: httpx.Client, url: str, params: Mapping[str, str] | None = None) -> httpx.Response:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response
