"""PSX stocks and indices via the `psxdata` library (MIT; scrapes the public PSX website).

NOTE: PSX's Terms of Use restrict automated retrieval and public display without PSX's prior
written permission. The project owner chose to use psxdata anyway (see README, "Data sources").
Keep usage polite: one run per day after market close, a short watchlist, psxdata's cache on.

psxdata returns floats; we serialize its DataFrame to CSV (the raw snapshot) and parse that
CSV into Decimals, so the stored raw payload is exactly what we parsed.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import structlog

from bachatcheck.config import get_settings
from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.records import InstrumentRef, PriceBarRecord, Record, to_decimal

log = structlog.get_logger()

NORMAL_WINDOW = timedelta(days=10)
INDEX_SYMBOLS = {"KSE100", "KSE30", "KMI30", "ALLSHR", "KMIALLSHR"}
INDEX_NAMES = {
    "KSE100": "KSE-100 Index",
    "KSE30": "KSE-30 Index",
    "KMI30": "KMI-30 Index (Shariah)",
    "ALLSHR": "KSE All Share Index",
    "KMIALLSHR": "KMI All Share Index (Shariah)",
}
SOURCE = "psxdata"


def instrument_for(symbol: str) -> InstrumentRef:
    if symbol in INDEX_SYMBOLS:
        return InstrumentRef(
            kind="index",
            symbol=symbol,
            name=INDEX_NAMES.get(symbol, symbol),
            source=SOURCE,
            is_shariah=symbol.startswith("KMI"),
        )
    # Name/sector enrichment comes later; the symbol is the stable identifier.
    return InstrumentRef(kind="stock", symbol=symbol, name=symbol, source=SOURCE)


def _fetch_frame(symbol: str, start: date, end: date) -> Any:
    import psxdata  # heavy import (pandas/pyarrow), so only when actually fetching

    return psxdata.stocks(symbol, start=start, end=end)


class PsxProvider(Provider):
    name = "psx"

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        start = ctx.start or ctx.as_of - NORMAL_WINDOW
        symbols = ctx.options.get("symbols")
        watchlist = (
            [s.strip().upper() for s in symbols.split(",")]
            if symbols
            else get_settings().psx_symbol_list
        )
        payloads = []
        for symbol in watchlist:
            try:
                frame = _fetch_frame(symbol, start, ctx.as_of)
            except Exception as exc:
                ctx.errors.append(f"{symbol}: {type(exc).__name__}: {exc}")
                log.warning("psx.symbol_failed", symbol=symbol, error=str(exc))
                continue
            if frame is None or len(frame) == 0:
                ctx.errors.append(f"{symbol}: no rows (unknown or delisted symbol?)")
                continue
            payloads.append(
                RawPayload(
                    source=self.name,
                    url=f"psxdata://stocks/{symbol}?start={start}&end={ctx.as_of}",
                    content=frame.to_csv(index=False).encode("utf-8"),
                    content_type="text/csv",
                )
            )
        return payloads

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        symbol = payload.url.removeprefix("psxdata://stocks/").split("?", 1)[0]
        instrument = instrument_for(symbol)
        reader = csv.DictReader(io.StringIO(payload.content.decode("utf-8")))
        required = {"date", "open", "high", "low", "close", "volume"}
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise ValueError(f"psxdata CSV missing columns; got {reader.fieldnames}")

        records: list[Record] = []
        for row in reader:
            close = to_decimal(row["close"])
            if close is None:
                continue
            volume = to_decimal(row["volume"])
            records.append(
                PriceBarRecord(
                    instrument=instrument,
                    date=date.fromisoformat(row["date"][:10]),
                    open=to_decimal(row["open"]),
                    high=to_decimal(row["high"]),
                    low=to_decimal(row["low"]),
                    close=close,
                    volume=int(volume) if volume is not None else None,
                    source=SOURCE,
                )
            )
        return records
