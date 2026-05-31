"""Microsoft Graph connector — mocked for hackathon, real-shaped for production.

Shape matches the real Graph SDK: delta token, paginated discovery, drive item ids,
owner from `createdBy.user.displayName`. Swap the mock data source for an actual
GraphServiceClient and the rest of the pipeline doesn't care.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from .base import BaseConnector, ConnectorEvent
from .filesystem import FileSystemConnector

DEPT_OWNERS = {
    "Finance": "anna.becker@bosch.example",
    "IT": "tobias.wagner@bosch.example",
    "Compliance": "miriam.braun@bosch.example",
    "Procurement": "jonas.keller@bosch.example",
    "HR": "elena.fischer@bosch.example",
    "General": "support@bosch.example",
    "Templates": "templates@bosch.example",
}


class GraphConnector(BaseConnector):
    """Mocked Graph adapter: walks `data/files/` but presents items as if they came
    from Microsoft Graph (`sharepoint`/`onedrive` source, business owner emails).
    """

    source = "sharepoint"

    def __init__(self, root: Path, site_id: str = "bosch.sharepoint.com,demo"):
        self.site_id = site_id
        self._fs = FileSystemConnector(root)
        self._scan_started_at: float | None = None

    async def discover(self, delta_token: str | None = None) -> AsyncIterator[ConnectorEvent]:
        self._scan_started_at = time.time()
        async for ev in self._fs.discover(delta_token=delta_token):
            dept = Path(ev.path).parent.name
            yield ConnectorEvent(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"graph://{self.site_id}/{ev.path}")),
                source="sharepoint",
                path=f"/{dept}/{Path(ev.path).name}",
                owner=DEPT_OWNERS.get(dept, "unknown@bosch.example"),
                mime=ev.mime,
                size_bytes=ev.size_bytes,
                # In real Graph this would be the drive-item content URL. We resolve
                # the local underlying path on read_bytes() instead.
                fetch_url=f"https://graph.microsoft.com/v1.0/sites/{self.site_id}/drive/items/{ev.id}/content",
            )
            await asyncio.sleep(0)

    async def read_bytes(self, event: ConnectorEvent) -> bytes:
        # Real impl: GraphServiceClient.sites.by_site_id(...).drive.items.by_item_id(...).content.get()
        # Mock: resolve back to local file
        local = Path(self._fs.root) / event.path.lstrip("/")
        return await asyncio.to_thread(local.read_bytes)

    async def next_delta_token(self) -> str:
        return str(self._scan_started_at or time.time())
