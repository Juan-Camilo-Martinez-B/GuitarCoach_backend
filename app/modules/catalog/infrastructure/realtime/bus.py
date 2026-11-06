"""Aviso de trabajos. Redis reparte el mensaje; si no está, se queda en este proceso."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.modules.catalog.domain.scrape_job import ScrapeJob

logger = logging.getLogger(__name__)

TERMINAL = frozenset({"done", "failed"})


class EventBus(Protocol):
    async def publish(self, channel: str, payload: dict[str, object]) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict[str, object]]: ...

    async def aclose(self) -> None: ...


def job_channel(job_id: UUID) -> str:
    return f"guitarcoach:job:{job_id}"


def job_payload(job: ScrapeJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "status": job.status,
        "song_id": job.song_id,
        "error": job.error,
    }


async def announce_job(bus: EventBus, job: ScrapeJob) -> None:
    """Publica el cierre del trabajo. Un fallo de Redis no deshace la importación."""
    if job.status not in TERMINAL:
        return
    try:
        await bus.publish(job_channel(job.id), job_payload(job))
    except Exception:
        logger.warning("No se pudo avisar el trabajo %s.", job.id)


class MemoryEventBus:
    """Entrega los avisos a los sockets de este proceso. Las pruebas lo usan."""

    def __init__(self) -> None:
        self._channels: dict[str, list[asyncio.Queue[dict[str, object]]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    async def publish(self, channel: str, payload: dict[str, object]) -> None:
        self._put(channel, payload)

    def publish_soon(self, channel: str, payload: dict[str, object]) -> None:
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._put, channel, payload)

    def _put(self, channel: str, payload: dict[str, object]) -> None:
        for queue in list(self._channels.get(channel, [])):
            queue.put_nowait(payload)

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self._loop = asyncio.get_running_loop()
        self._channels.setdefault(channel, []).append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            waiters = self._channels.get(channel, [])
            if queue in waiters:
                waiters.remove(queue)

    async def aclose(self) -> None:
        self._channels.clear()


class RedisEventBus:
    """Publica en Redis para que cualquier instancia entregue el aviso."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    async def publish(self, channel: str, payload: dict[str, object]) -> None:
        await self._client.publish(channel, json.dumps(payload))

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, object]]:
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if not isinstance(message, dict) or message.get("type") != "message":
                    continue
                raw = message.get("data")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                if not isinstance(raw, str):
                    continue
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    yield parsed
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def aclose(self) -> None:
        await self._client.aclose()


async def open_event_bus(url: str) -> EventBus:
    """Conecta a Redis si hay URL y responde. Si no, el proceso se avisa a sí mismo."""
    if not url.strip():
        return MemoryEventBus()
    client: Redis = Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=0.5,
    )
    try:
        await asyncio.wait_for(client.ping(), timeout=0.5)
    except Exception:
        await client.aclose()
        logger.warning("Redis no responde. Los avisos del trabajo quedan en este proceso.")
        return MemoryEventBus()
    return RedisEventBus(client)
