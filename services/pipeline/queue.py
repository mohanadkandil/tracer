"""Async work queue + worker pool.

For the demo: in-process asyncio.Queue. Same API + semantics as Redis Streams /
NATS JetStream so the swap is one file. Workers are async tasks that pull events
and run them through the full tiered routing pipeline.

Production diff: replace `asyncio.Queue` with a Redis Streams consumer group.
The worker body stays the same.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ..config import QUEUE_MAX_SIZE, WORKER_COUNT
from ..connectors.base import ConnectorEvent

log = logging.getLogger("pipeline.queue")


@dataclass(slots=True)
class WorkItem:
    event: ConnectorEvent
    enqueued_at: float


@dataclass(slots=True)
class QueueStats:
    enqueued: int = 0
    processed: int = 0
    deduped: int = 0
    failed: int = 0
    in_flight: int = 0


class ScanQueue:
    """Bounded async queue with a worker pool. The pool calls a user-provided
    `process` coroutine for each WorkItem. Backpressure comes for free from
    `Queue.put()` blocking when full.
    """

    def __init__(self, process: Callable[[WorkItem], Awaitable[None]], workers: int = WORKER_COUNT):
        self._q: asyncio.Queue[WorkItem | None] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._workers: list[asyncio.Task] = []
        self._process = process
        self._n_workers = workers
        self.stats = QueueStats()
        self._stopped = False

    async def start(self) -> None:
        if self._workers:
            return
        for i in range(self._n_workers):
            self._workers.append(asyncio.create_task(self._run_worker(i)))

    async def stop(self) -> None:
        self._stopped = True
        for _ in self._workers:
            await self._q.put(None)  # sentinel
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def submit(self, event: ConnectorEvent) -> None:
        await self._q.put(WorkItem(event=event, enqueued_at=time.time()))
        self.stats.enqueued += 1

    async def drain(self) -> None:
        """Block until everything currently queued is processed."""
        await self._q.join()

    async def _run_worker(self, idx: int) -> None:
        while not self._stopped:
            item = await self._q.get()
            if item is None:
                self._q.task_done()
                return
            self.stats.in_flight += 1
            try:
                await self._process(item)
                self.stats.processed += 1
            except Exception:
                self.stats.failed += 1
                log.exception("worker %d failed processing %s", idx, item.event.path)
            finally:
                self.stats.in_flight -= 1
                self._q.task_done()

    def snapshot(self) -> dict:
        return {
            "enqueued": self.stats.enqueued,
            "processed": self.stats.processed,
            "deduped": self.stats.deduped,
            "failed": self.stats.failed,
            "in_flight": self.stats.in_flight,
            "depth": self._q.qsize(),
            "workers": self._n_workers,
        }
