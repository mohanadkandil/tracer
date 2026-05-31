"""Real filesystem connector. Walks a directory tree, yields events.

Owner attribution = file's POSIX owner uid resolved to username, falls back to
parent folder name when uid lookup fails. Mimics OneDrive's "Master of Data" idea.

Delta sync = compare mtime against last_token timestamp; only emit changed files.
"""

from __future__ import annotations

import asyncio
import mimetypes
import pwd
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from .base import BaseConnector, ConnectorEvent

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules", ".DS_Store"}
TEXT_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
    "message/rfc822",  # .eml
}


class FileSystemConnector(BaseConnector):
    source = "filesystem"

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"root not a directory: {self.root}")
        self._scan_started_at: float | None = None

    async def discover(self, delta_token: str | None = None) -> AsyncIterator[ConnectorEvent]:
        self._scan_started_at = time.time()
        cutoff = float(delta_token) if delta_token else 0.0

        for path in self._safe_walk(self.root):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime <= cutoff:
                continue
            mime, _ = mimetypes.guess_type(path.name)
            if mime not in TEXT_MIMES and path.suffix.lower() not in {".eml", ".txt"}:
                continue
            yield ConnectorEvent(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"fs://{path}")),
                source="filesystem",
                path=str(path),
                owner=self._owner(path, stat.st_uid),
                mime=mime or "application/octet-stream",
                size_bytes=stat.st_size,
                fetch_url=None,
            )
            # Co-operate with the event loop on busy trees
            await asyncio.sleep(0)

    async def read_bytes(self, event: ConnectorEvent) -> bytes:
        return await asyncio.to_thread(Path(event.path).read_bytes)

    async def next_delta_token(self) -> str:
        return str(self._scan_started_at or time.time())

    def _safe_walk(self, root: Path):
        """Recursive walk that skips junk and refuses to follow symlink loops."""
        seen: set[Path] = set()

        def _walk(d: Path):
            try:
                real = d.resolve()
            except OSError:
                return
            if real in seen:
                return
            seen.add(real)
            try:
                entries = list(d.iterdir())
            except OSError:
                return
            for entry in entries:
                if entry.name in SKIP_DIRS:
                    continue
                if entry.is_symlink():
                    # Allow symlinks but rely on `seen` to prevent loops
                    pass
                if entry.is_dir():
                    yield from _walk(entry)
                else:
                    yield entry

        yield from _walk(root)

    @staticmethod
    def _owner(path: Path, uid: int) -> str:
        try:
            return pwd.getpwuid(uid).pw_name
        except KeyError:
            return path.parent.name  # fall back to "Master of Data"-ish heuristic
