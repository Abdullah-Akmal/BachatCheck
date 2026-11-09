"""Loads versioned tax assumptions from data/tax_rules.yaml into the tax_rules table."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from bachatcheck.config import get_settings
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import Record, TaxRuleRecord, to_decimal


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


class TaxRulesProvider(Provider):
    name = "tax_rules"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        path = Path(ctx.options.get("file") or get_settings().tax_rules_path)
        return [
            RawPayload(
                source=self.name,
                url=f"file://{path.name}",
                content=path.read_bytes(),
                content_type="application/yaml",
            )
        ]

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        doc = yaml.safe_load(payload.content) or {}
        records: list[Record] = []
        for rule in doc.get("rules", []):
            effective_from = _date(rule["effective_from"])
            if effective_from is None:
                raise ValueError(f"rule {rule} has no effective_from")
            records.append(
                TaxRuleRecord(
                    asset_class=rule["asset_class"],
                    tax_type=rule["tax_type"],
                    filer_status=rule.get("filer_status", "filer"),
                    effective_from=effective_from,
                    effective_to=_date(rule.get("effective_to")),
                    # Rates are strings in YAML so they parse straight to Decimal.
                    rate=to_decimal(rule.get("rate")),
                    source_url=rule.get("source_url"),
                    notes=rule.get("notes"),
                    verified=bool(rule.get("verified", False)),
                )
            )
        return records
