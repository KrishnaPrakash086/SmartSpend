# Server-Sent Events manager — in-process pub/sub fan-out to connected browser clients
import asyncio
import json
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

logger = structlog.get_logger()

router = APIRouter(tags=["Events"])


class EventStreamManager:
    def __init__(self):
        self._clients: list[asyncio.Queue] = []

    # Each subscriber gets its own asyncio.Queue; generator yields until client disconnects
    async def subscribe(self) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue = asyncio.Queue()
        self._clients.append(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        finally:
            # Cleanup on disconnect to prevent memory leaks from abandoned queues
            await self.disconnect(queue)

    # Fan-out: broadcast event to all connected clients; prune any with full queues (stale connections)
    async def publish(self, event_type: str, data: dict) -> None:
        payload = {"event": event_type, "data": json.dumps(data)}
        disconnected: list[asyncio.Queue] = []
        for queue in self._clients:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                disconnected.append(queue)
        for queue in disconnected:
            self._clients.remove(queue)
        if self._clients:
            logger.debug("sse_event_published", event_type=event_type, clients=len(self._clients))

    async def disconnect(self, queue: asyncio.Queue) -> None:
        if queue in self._clients:
            self._clients.remove(queue)


event_manager = EventStreamManager()


@router.get("/events/stream")
async def event_stream():
    return EventSourceResponse(event_manager.subscribe())
