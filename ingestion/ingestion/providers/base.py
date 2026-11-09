"""The provider contract every data source implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar

from ingestion.records import Record


@dataclass(frozen=True)
class RawPayload:
    """A raw response, persisted to raw_snapshots *before* parsing.

    `url` must never contain secrets — providers build it without API keys.
    """

    source: str
    url: str
    content: bytes
    content_type: str


@dataclass
class FetchContext:
    as_of: date
    # Earliest date to fetch. None means "the provider's normal recent window".
    start: date | None = None
    options: dict[str, str] = field(default_factory=dict)
    # Non-fatal fetch problems (e.g. one series out of nine failed). Makes the run "partial".
    errors: list[str] = field(default_factory=list)


class Provider(ABC):
    """fetch() returns raw payloads; parse() turns one payload into normalized records.

    Keeping the two apart means a parser bug never loses data: raw payloads are stored
    first and can be re-parsed later.
    """

    name: ClassVar[str]

    @abstractmethod
    def fetch(self, ctx: FetchContext) -> Sequence[RawPayload]: ...

    @abstractmethod
    def parse(self, payload: RawPayload) -> Sequence[Record]: ...
