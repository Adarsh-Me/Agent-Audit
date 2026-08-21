"""In-process SSE event bus — runner progress → browser (TECHSPEC §11).

Events per run: progress · trial · e203_cost_cap · complete. Heartbeat every 15 s.
Single-process deployment scope (hackathon); swap for Redis pub/sub if multi-worker.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict

HEARTBEAT_S = 15


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._last: dict[str, dict] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        if q in self._subs[run_id]:
            self._subs[run_id].remove(q)

    async def publish(self, run_id: str, event: dict) -> None:
        event = {**event, "ts": time.time()}
        self._last[run_id] = event
        for q in list(self._subs.get(run_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop rather than block the runner

    def last(self, run_id: str) -> dict | None:
        return self._last.get(run_id)


bus = EventBus()


def sse_format(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
