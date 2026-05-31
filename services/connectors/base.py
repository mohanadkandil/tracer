"""Connector abstraction. Same interface for filesystem demos and Microsoft Graph prod.

A connector emits ConnectorEvent items via an async iterator. Each event describes
one discoverable file: a stable id, source kind, path or URL, owner attribution, and
how to fetch bytes. The pipeline doesn't know if events came from local disk, Graph
API, or a Slack export — that's the whole point.

`delta_token` enables resumable / incremental sync (matches Graph API semantics).
For filesystem connector we hash mtimes to fake it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["filesystem", "sharepoint", "onedrive", "fileshare", "slack"]


@dataclass(slots=True)
class ConnectorEvent:
    id: str
    source: SourceKind
    path: str  # local path OR drive item URL
    owner: str | None
    mime: str | None
    size_bytes: int | None
    fetch_url: str | None = None  # for remote sources; None = local read


class BaseConnector(ABC):
    """Adapter contract. Same shape for filesystem and Microsoft Graph."""

    source: SourceKind

    @abstractmethod
    def discover(self, delta_token: str | None = None) -> AsyncIterator[ConnectorEvent]:
        """Yield events. Pass last delta_token for incremental scan."""
        ...

    @abstractmethod
    async def read_bytes(self, event: ConnectorEvent) -> bytes:
        """Fetch raw file bytes for a given event."""
        ...

    @abstractmethod
    async def next_delta_token(self) -> str:
        """Token to persist after a discover() run completes."""
        ...
