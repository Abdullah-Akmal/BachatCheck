from collections.abc import Iterator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from bachatcheck.db import optional_session
from bachatcheck.main import create_app


def _client_with_session(session: MagicMock | None) -> TestClient:
    app = create_app()

    def override() -> Iterator[MagicMock | None]:
        yield session

    app.dependency_overrides[optional_session] = override
    return TestClient(app)


def test_health_degraded_not_500_when_db_misconfigured() -> None:
    # e.g. DATABASE_URL missing or unparseable: optional_session yields None.
    resp = _client_with_session(None).get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "unavailable"


def test_health_ok_when_db_reachable() -> None:
    client = _client_with_session(MagicMock())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["database"] == "ok"


def test_health_degraded_when_db_down() -> None:
    session = MagicMock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
    client = _client_with_session(session)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "degraded", "version": "0.1.0", "database": "unavailable"}


def test_openapi_docs_enabled() -> None:
    client = TestClient(create_app())
    assert client.get("/openapi.json").status_code == 200


def test_cors_allows_only_configured_origin() -> None:
    client = TestClient(create_app())
    allowed = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    blocked = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in blocked.headers
