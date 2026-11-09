"""The provider contract every data source implements."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, ClassVar


@dataclass(frozen=True)
class RawPayload:
    """A raw response, persisted to raw_snapshots *before* parsing."""

    source: str
    url: str
    content: bytes
    content_type: str


class Provider(ABC):
    """fetch() returns raw payloads; parse() turns them into normalized records.

    Keeping the two steps apart means a parser bug never loses data: raw payloads are
    stored first and can be re-parsed later.
    """

    name: ClassVar[str]

    @abstractmethod
    def fetch(self, as_of: date) -> Sequence[RawPayload]: ...

    @abstractmethod
    def parse(self, payload: RawPayload) -> Sequence[dict[str, Any]]: ...
