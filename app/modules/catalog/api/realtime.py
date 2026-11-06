"""Socket de un trabajo. El navegador escucha; la consulta REST sigue valiendo."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import cast
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.modules.catalog.domain.scrape_job import ScrapeJob
from app.modules.catalog.infrastructure.realtime.bus import (
    TERMINAL,
    EventBus,
    job_channel,
    job_payload,
)
from app.modules.catalog.infrastructure.sql import SqlJobRepository
from app.modules.catalog.ports import CatalogStore
from app.modules.identity.public import bearer_user_id
from app.shared.config import Settings
from app.shared.errors import AuthenticationError

router = APIRouter(tags=["realtime"])


def _bus(websocket: WebSocket) -> EventBus:
    return cast(EventBus, websocket.app.state.events)


def _allowed_origin(websocket: WebSocket, settings: Settings) -> bool:
    origin = websocket.headers.get("origin")
    return origin is None or origin in settings.cors_origins


async def _read_job(websocket: WebSocket, job_id: UUID) -> ScrapeJob | None:
    factory = getattr(websocket.app.state, "session_factory", None)
    if factory is None:
        return await cast(CatalogStore, websocket.app.state.uow).jobs.get(job_id)
    async with factory() as session:
        return await SqlJobRepository(session).get(job_id)


async def _pump(websocket: WebSocket, bus: EventBus, job_id: UUID) -> None:
    async for event in bus.subscribe(job_channel(job_id)):
        await websocket.send_json(event)
        if event.get("status") in TERMINAL:
            return


@router.websocket("/ws/jobs/{job_id}")
async def job_events(websocket: WebSocket, job_id: UUID) -> None:
    settings = websocket.app.state.settings
    if not isinstance(settings, Settings) or not _allowed_origin(websocket, settings):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        body = json.loads(raw)
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise AuthenticationError("Falta el token.")
        user_id = bearer_user_id(f"Bearer {token}", settings)
        job = await _read_job(websocket, job_id)
        if job is None:
            await websocket.send_json({"error": "El trabajo no existe."})
            await websocket.close(code=1008)
            return
        if job.user_id is not None and job.user_id != user_id:
            await websocket.send_json({"error": "El trabajo no existe."})
            await websocket.close(code=1008)
            return
        snapshot = job_payload(job)
        bus = _bus(websocket)
        task = asyncio.create_task(_pump(websocket, bus, job_id))
        try:
            await websocket.send_json(snapshot)
            if snapshot["status"] in TERMINAL:
                return
            await task
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    except (TimeoutError, json.JSONDecodeError, AuthenticationError, WebSocketDisconnect):
        await websocket.close(code=1008)
