"""PKR exchange rates from Frankfurter (v2 API), using its State Bank of Pakistan provider.

SBP rates are the daily average of banks' floating rates. Frankfurter publishes them monthly,
so the normal window looks back 45 days to pick up the latest batch.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta
from urllib.parse import urlencode

from ingestion import http
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import FxRateRecord, Record, to_decimal

BASE_URL = "https://api.frankfurter.dev/v2/rates"
PROVIDER = "SBP"
BASES = ("USD",)  # extend with e.g. "SAR", "AED", "GBP" if needed
QUOTE = "PKR"
NORMAL_WINDOW = timedelta(days=45)
# Frankfurter's SBP data starts here.
EARLIEST = date(2013, 7, 2)


class FrankfurterProvider(Provider):
    name = "frankfurter"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        start = max(ctx.start or ctx.as_of - NORMAL_WINDOW, EARLIEST)
        payloads = []
        with http.make_client() as client:
            for base in BASES:
                params = {
                    "base": base,
                    "quotes": QUOTE,
                    "providers": PROVIDER,
                    "from": start.isoformat(),
                    "to": ctx.as_of.isoformat(),
                }
                resp = http.get(client, BASE_URL, params)
                payloads.append(
                    RawPayload(
                        source=self.name,
                        url=f"{BASE_URL}?{urlencode(params)}",
                        content=resp.content,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
                )
        return payloads

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        data = json.loads(payload.content)
        if not isinstance(data, list):
            raise ValueError(f"expected a JSON list, got {type(data).__name__}")
        records: list[Record] = []
        for row in data:
            rate = to_decimal(row["rate"])
            if rate is None:
                continue
            records.append(
                FxRateRecord(
                    base=row["base"],
                    quote=row["quote"],
                    date=date.fromisoformat(row["date"]),
                    rate=rate,
                    provider=f"frankfurter:{PROVIDER}",
                )
            )
        return records
