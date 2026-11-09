"""CLI entry point.

    python -m ingestion list
    python -m ingestion run <source> [--date YYYY-MM-DD]
        [--file PATH] [--symbols A,B] [--series X,Y]
    python -m ingestion backfill <source> --from YYYY-MM-DD [--to YYYY-MM-DD]

Exit codes: 0 success, 1 failed, 2 usage error, 3 partial (some rows/series failed).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date

import structlog

from bachatcheck.config import get_settings
from bachatcheck.log_config import configure_logging
from ingestion.providers import REGISTRY
from ingestion.providers.base import FetchContext
from ingestion.records import today_pkt

log = structlog.get_logger()

BACKFILLABLE = {"sbp", "frankfurter", "psx"}
EXIT = {"success": 0, "failed": 1, "partial": 3}


def _add_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--file", help="mufap/gold/tax_rules: read this file instead of the default")
    p.add_argument("--symbols", help="psx: comma-separated symbols (default: PSX_SYMBOLS)")
    p.add_argument("--series", help="sbp: comma-separated series codes, e.g. CPI_YOY,TBILL_3M")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion", description="BachatCheck ingestion jobs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List available sources")

    run = sub.add_parser("run", help="Run one source's daily job")
    run.add_argument("source")
    run.add_argument("--date", type=date.fromisoformat, default=None, help="As-of date")
    _add_options(run)

    bf = sub.add_parser("backfill", help=f"Fetch history ({', '.join(sorted(BACKFILLABLE))})")
    bf.add_argument("source")
    bf.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    bf.add_argument("--to", dest="end", type=date.fromisoformat, default=None)
    _add_options(bf)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    if args.command == "list":
        for name in sorted(REGISTRY):
            print(name)
        return 0

    if args.source not in REGISTRY:
        log.error("ingestion.unknown_source", source=args.source, available=sorted(REGISTRY))
        return 2
    if args.command == "backfill" and args.source not in BACKFILLABLE:
        log.error("ingestion.not_backfillable", source=args.source)
        return 2

    options = {k: v for k in ("file", "symbols", "series") if (v := getattr(args, k))}
    if args.command == "backfill":
        ctx = FetchContext(as_of=args.end or today_pkt(), start=args.start, options=options)
    else:
        ctx = FetchContext(as_of=args.date or today_pkt(), options=options)

    # Imported here so `list` and usage errors work without a database driver.
    from bachatcheck.db import _session_factory
    from ingestion.runner import run_job

    result = run_job(REGISTRY[args.source](), _session_factory(), ctx)
    return EXIT[result.status]
