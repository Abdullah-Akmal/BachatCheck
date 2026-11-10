import pytest

from bachatcheck.config import Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (
            "postgresql://u:p@ep-x.neon.tech/db?sslmode=require",
            "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require",
        ),
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg://u:p@db:5432/db", "postgresql+psycopg://u:p@db:5432/db"),
    ],
)
def test_database_url_uses_psycopg3(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected
