"""Gold price in PKR per tola (24k), from a manually maintained CSV in the repo.

No free, reliable source of Pakistani local gold prices was found, so the UI labels gold as
"manually updated". CSV columns: date (YYYY-MM-DD), price_pkr, source_note.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from bachatcheck.config import get_settings
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import InstrumentRef, PriceBarRecord, Record, to_decimal

SOURCE = "manual_csv"
GOLD = InstrumentRef(
    kind="gold",
    symbol="GOLD24K_TOLA",
    name="Gold 24k (per tola, 11.664 g)",
    source=SOURCE,
    is_shariah=True,
)


class GoldCsvProvider(Provider):
    name = "gold"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        path = Path(ctx.options.get("file") or get_settings().gold_csv_path)
        return [
            RawPayload(
                source=self.name,
                url=f"file://{path.name}",
                content=path.read_bytes(),
                content_type="text/csv",
            )
        ]

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        reader = csv.DictReader(io.StringIO(payload.content.decode("utf-8-sig")))
        if reader.fieldnames is None or not {"date", "price_pkr"} <= set(reader.fieldnames):
            raise ValueError("gold CSV needs 'date' and 'price_pkr' columns")
        records: list[Record] = []
        for row in reader:
            price = to_decimal(row["price_pkr"])
            if price is None:
                continue
            records.append(
                PriceBarRecord(
                    instrument=GOLD,
                    date=date.fromisoformat(row["date"].strip()),
                    close=price,
                    source=SOURCE,
                )
            )
        return records
