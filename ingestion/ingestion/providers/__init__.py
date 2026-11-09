"""Data-source providers. Each implements `Provider` and is registered in `REGISTRY`."""

from ingestion.providers.base import Provider

# Filled in milestone 2: "sbp", "frankfurter", "psx", "mufap", "gold".
REGISTRY: dict[str, type[Provider]] = {}
