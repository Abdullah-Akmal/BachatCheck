"""Synthetic demo data so a fresh clone works without touching any live source.

    docker compose run --rm ingestion seed           # load (refuses if real data exists)
    docker compose run --rm ingestion seed --clear   # remove it again

Everything here is MADE UP: deterministic (fixed random seed) and plausible-looking, but not real
prices, rates or inflation. Rows are written with source "demo_seed", and the site shows a
"synthetic demo data" banner while they exist. Demo stocks use obviously fake tickers.
"""

from __future__ import annotations

import itertools
import json
import math
import random
from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from ingestion.providers.base import FetchContext, Provider, RawPayload
from ingestion.providers.gold import GOLD
from ingestion.providers.psx import instrument_for
from ingestion.providers.sbp import SERIES
from ingestion.records import (
    FxRateRecord,
    InstrumentRef,
    MacroObservationRecord,
    MacroSeriesDef,
    PriceBarRecord,
    Record,
)

SOURCE = "demo_seed"
START = date(2016, 7, 1)
SEED = 20261110

DEMO_STOCKS = {
    "DEMOA": ("Demo Stock A (synthetic)", 1.2),  # (name, beta to the index)
    "DEMOB": ("Demo Stock B (synthetic)", 0.7),
}

# Synthetic policy-rate path (percent), stepped like a real easing/tightening cycle.
POLICY_PATH: list[tuple[date, float]] = [
    (date(2016, 7, 1), 6.0),
    (date(2018, 6, 1), 7.5),
    (date(2019, 2, 1), 10.5),
    (date(2019, 8, 1), 13.0),
    (date(2020, 4, 1), 9.0),
    (date(2020, 7, 1), 7.0),
    (date(2021, 10, 1), 8.5),
    (date(2022, 2, 1), 11.0),
    (date(2022, 8, 1), 15.0),
    (date(2023, 5, 1), 20.0),
    (date(2024, 7, 1), 18.0),
    (date(2024, 11, 1), 14.0),
    (date(2025, 5, 1), 11.5),
    (date(2026, 4, 1), 12.0),
]
# Synthetic USD/PKR anchors; daily values interpolate in log space plus noise.
FX_ANCHORS: list[tuple[date, float]] = [
    (date(2016, 7, 1), 105.0),
    (date(2018, 12, 31), 138.0),
    (date(2019, 7, 1), 160.0),
    (date(2021, 6, 30), 158.0),
    (date(2022, 12, 31), 225.0),
    (date(2023, 9, 1), 300.0),
    (date(2024, 6, 30), 279.0),
    (date(2030, 1, 1), 285.0),
]


def _business_days(start: date, end: date) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _month_ends(start: date, end: date) -> list[date]:
    out: list[date] = []
    y, m = start.year, start.month
    while True:
        nxt = date(y + (m == 12), m % 12 + 1, 1)
        d = nxt - timedelta(days=1)
        if d > end:
            return out
        out.append(d)
        y, m = nxt.year, nxt.month


def _step(path: list[tuple[date, float]], d: date) -> float:
    value = path[0][1]
    for when, v in path:
        if when <= d:
            value = v
    return value


def _log_interp(anchors: list[tuple[date, float]], d: date) -> float:
    for (d0, v0), (d1, v1) in itertools.pairwise(anchors):
        if d0 <= d <= d1:
            t = (d - d0).days / max((d1 - d0).days, 1)
            return math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0)))
    return anchors[-1][1]


def _r(x: float, places: int) -> str:
    return str(round(x, places))


def generate(as_of: date) -> dict[str, Any]:
    """Build the whole synthetic dataset as plain JSON-able data (decimal strings)."""
    rng = random.Random(SEED)  # noqa: S311 (synthetic data, not security)
    days = _business_days(START, as_of)
    months = _month_ends(START, as_of)
    macro: dict[str, list[list[str]]] = {}

    # CPI: month-on-month % with seasonality and an inflation surge in 2022-23.
    mom, yoy, index = [], [], [100.0]
    for i, m in enumerate(months):
        surge = 1.5 if date(2022, 1, 1) <= m <= date(2023, 12, 31) else 0.0
        v = 0.55 + 0.25 * math.sin(2 * math.pi * i / 12) + surge + rng.gauss(0, 0.25)
        mom.append([m.isoformat(), _r(v, 2)])
        index.append(index[-1] * (1 + round(v, 2) / 100))
        if i >= 12:
            yoy.append([m.isoformat(), _r((index[-1] / index[-13] - 1) * 100, 1)])
    macro["CPI_MOM"], macro["CPI_YOY"] = mom, yoy

    macro["POLICY_RATE"] = [[d.isoformat(), _r(v, 2)] for d, v in POLICY_PATH if d <= as_of]
    for code, spread in (("TBILL_3M", -0.15), ("TBILL_6M", -0.05), ("TBILL_12M", 0.05)):
        auctions = days[::10]  # roughly fortnightly
        macro[code] = [
            [d.isoformat(), _r(_step(POLICY_PATH, d) + spread + rng.gauss(0, 0.12), 4)]
            for d in auctions
        ]
    for code, spread in (("KIBOR_3M", 0.2), ("KIBOR_6M", 0.3)):
        macro[code] = [
            [d.isoformat(), _r(_step(POLICY_PATH, d) + spread + rng.gauss(0, 0.05), 2)]
            for d in days[::5]
        ]
    macro["DEPOSIT_RATE_FRESH"] = [
        [m.isoformat(), _r(_step(POLICY_PATH, m) * 0.36, 2)] for m in months
    ]
    macro["DEPOSIT_RATE_OUTSTANDING"] = [
        [m.isoformat(), _r(_step(POLICY_PATH, m) * 0.46, 2)] for m in months
    ]

    fx = [
        [d.isoformat(), _r(_log_interp(FX_ANCHORS, d) * (1 + rng.gauss(0, 0.002)), 4)] for d in days
    ]

    # Indices and stocks: correlated geometric random walks with daily OHLC.
    bars: dict[str, list[list[str]]] = {}
    levels = {"KSE100": 38_000.0, "KMI30": 66_000.0, "DEMOA": 120.0, "DEMOB": 45.0}
    betas = {"KSE100": 1.0, "KMI30": 1.05, **{s: b for s, (_, b) in DEMO_STOCKS.items()}}
    for sym in levels:
        bars[sym] = []
    for d in days:
        market = rng.gauss(0.0005, 0.011)
        for sym, level in levels.items():
            ret = betas[sym] * market + rng.gauss(0, 0.004 if sym in ("KSE100", "KMI30") else 0.012)
            close = level * math.exp(ret)
            open_ = level * math.exp(rng.gauss(0, 0.003))
            high = max(open_, close) * (1 + abs(rng.gauss(0, 0.004)))
            low = min(open_, close) * (1 - abs(rng.gauss(0, 0.004)))
            volume = int(
                abs(rng.gauss(1.5e8 if sym == "KSE100" else 3e6, 5e7 if sym == "KSE100" else 1e6))
            )
            bars[sym].append(
                [d.isoformat(), _r(open_, 2), _r(high, 2), _r(low, 2), _r(close, 2), str(volume)]
            )
            levels[sym] = close

    gold = [
        [
            m.isoformat(),
            _r(
                _log_interp([(START, 52_000.0), (date(2030, 1, 1), 520_000.0)], m)
                * (1 + rng.gauss(0, 0.02)),
                0,
            ),
        ]
        for m in months
    ]
    return {
        "_note": "SYNTHETIC demo data — not real prices or rates.",
        "macro": macro,
        "fx": fx,
        "bars": bars,
        "gold": gold,
    }


class DemoSeedProvider(Provider):
    name = SOURCE

    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]:
        content = json.dumps(generate(ctx.as_of)).encode()
        return [RawPayload(self.name, "generated://demo_seed", content, "application/json")]

    def parse(self, payload: RawPayload) -> Sequence[Record]:
        data = json.loads(payload.content)
        series = {
            s.code: MacroSeriesDef(
                s.code, s.name, s.unit, s.frequency, SOURCE, s.source_key, s.description
            )
            for s in SERIES
        }
        records: list[Record] = []
        for code, points in data["macro"].items():
            for d, v in points:
                records.append(
                    MacroObservationRecord(series[code], date.fromisoformat(d), Decimal(v), SOURCE)
                )
        for d, v in data["fx"]:
            records.append(FxRateRecord("USD", "PKR", date.fromisoformat(d), Decimal(v), SOURCE))
        for sym, rows in data["bars"].items():
            inst = (
                InstrumentRef(kind="stock", symbol=sym, name=DEMO_STOCKS[sym][0], source=SOURCE)
                if sym in DEMO_STOCKS
                else instrument_for(sym)
            )
            for d, o, h, lo, c, v in rows:
                records.append(
                    PriceBarRecord(
                        instrument=inst,
                        date=date.fromisoformat(d),
                        open=Decimal(o),
                        high=Decimal(h),
                        low=Decimal(lo),
                        close=Decimal(c),
                        volume=int(v),
                        source=SOURCE,
                    )
                )
        for d, v in data["gold"]:
            records.append(
                PriceBarRecord(
                    instrument=GOLD, date=date.fromisoformat(d), close=Decimal(v), source=SOURCE
                )
            )
        return records
