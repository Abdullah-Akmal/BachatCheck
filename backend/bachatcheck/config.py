"""Application settings, loaded from environment variables (and a local .env file)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "postgresql+psycopg://bachatcheck:bachatcheck@localhost:5432/bachatcheck"
    # Comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_json: bool = Field(default=False, description="Emit JSON logs (use in production).")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
