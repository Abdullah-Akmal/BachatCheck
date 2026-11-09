"""CLI entry point: `python -m ingestion run <source>`."""

import argparse
from collections.abc import Sequence
from datetime import date

import structlog

from ingestion.providers import REGISTRY

log = structlog.get_logger()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingestion", description="BachatCheck ingestion jobs")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run one source's ingestion job")
    run.add_argument("source", help="Source name, e.g. sbp, frankfurter, psx, mufap")
    run.add_argument(
        "--date", type=date.fromisoformat, default=None, help="As-of date (YYYY-MM-DD)"
    )

    sub.add_parser("list", help="List available sources")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list":
        for name in sorted(REGISTRY):
            print(name)
        return 0

    if args.source not in REGISTRY:
        available = ", ".join(sorted(REGISTRY)) or "(none yet — added in milestone 2)"
        log.error("ingestion.unknown_source", source=args.source, available=available)
        return 2

    raise NotImplementedError("Job runner arrives in milestone 2")
