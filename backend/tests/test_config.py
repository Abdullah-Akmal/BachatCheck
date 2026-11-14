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
        # Pasted from a .env file into a dashboard: quotes, whitespace, even the key.
        ('"postgresql://u:p@ep-x.neon.tech/db?sslmode=require"',
         "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require"),
        ("  'postgres://u:p@host/db'\n", "postgresql+psycopg://u:p@host/db"),
        ('DATABASE_URL="postgresql://u:p@host/db"', "postgresql+psycopg://u:p@host/db"),
    ],
)  # fmt: skip
def test_database_url_uses_psycopg3(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected
