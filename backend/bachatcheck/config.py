"""Application settings, loaded from environment variables (and a local .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


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

    # --- Data display modes ---
    # MUFAP's terms forbid public display without written approval, so production uses demo data.
    funds_data_mode: Literal["real", "demo"] = "real"
    stocks_data_mode: Literal["real", "demo"] = "real"

    # --- Ingestion ---
    http_user_agent: str = (
        "BachatCheck/0.1 (education project; https://github.com/Abdullah-Akmal/BachatCheck)"
    )
    sbp_easydata_api_key: SecretStr | None = None
    # psxdata symbols fetched daily. KSE100 is stored as an index, the rest as stocks.
    psx_symbols: str = "KSE100,KMI30,OGDC,PPL,HBL,MCB,UBL,MEBL,LUCK,HUBC,FFC,SYS"
    # Root of the versioned data files (tax rules, gold CSV, demo data, MUFAP inbox).
    data_dir: Path = REPO_ROOT / "data"

    # --- Returns engine / API ---
    # Macro series used as the default bank-savings rate (users can override per request).
    savings_benchmark_series: str = "DEPOSIT_RATE_FRESH"
    # Requests per minute per client IP for /api/v1 (health is exempt).
    rate_limit_per_minute: int = 60
    # Seconds that heavy GET responses are cached in-process.
    cache_ttl_seconds: int = 300
    # Use the first X-Forwarded-For hop as the client IP (only behind a trusted proxy).
    trust_forwarded_for: bool = False

    @property
    def mufap_inbox_dir(self) -> Path:
        return self.data_dir / "mufap_inbox"

    @property
    def gold_csv_path(self) -> Path:
        return self.data_dir / "gold" / "gold_pkr_per_tola_24k.csv"

    @property
    def tax_rules_path(self) -> Path:
        return self.data_dir / "tax_rules.yaml"

    @property
    def demo_funds_path(self) -> Path:
        return self.data_dir / "demo" / "funds.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def psx_symbol_list(self) -> list[str]:
        return [s.strip().upper() for s in self.psx_symbols.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
