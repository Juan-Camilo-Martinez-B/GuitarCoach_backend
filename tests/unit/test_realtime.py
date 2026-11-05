"""El socket entrega el cierre de un trabajo. Sin Redis el aviso se queda en el proceso."""

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.domain.entities.scrape_job import ScrapeJob
from app.infrastructure.db.memory import InMemoryUnitOfWork
from app.infrastructure.realtime.bus import MemoryEventBus, RedisEventBus, job_channel
from app.main import create_app
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

SECRET = "secreto-de-prueba-con-longitud-suficiente"


def _client() -> TestClient:
    return TestClient(create_app(Settings(environment="local", jwt_secret=SECRET, redis_url="")))


def _token(client: TestClient) -> str:
    created = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "secreto-largo", "display_name": "Ana"},
    )
    assert created.status_code == 201
    logged = client.post(
        "/auth/login",
        json={"email": "ana@example.com", "password": "secreto-largo"},
    )
    token = logged.json().get("access_token")
    assert isinstance(token, str)
    return token


async def _pending(client: TestClient, owner: str | None = None) -> ScrapeJob:
    from app.application.security import JwtTokenIssuer, SystemClock

    user_id = None
    if owner is not None:
        user_id = JwtTokenIssuer(SECRET, "HS256", 30, SystemClock()).read_user_id(owner)
    now = datetime.now(UTC)
    job = ScrapeJob(
        id=uuid4(),
        user_id=user_id,
        song_id=None,
        status="pending",
        query="estudio",
        error=None,
        created_at=now,
        updated_at=now,
    )
    uow = client.app.state.uow
    assert isinstance(uow, InMemoryUnitOfWork)
    await uow.jobs.add(job)
    return job


def test_sin_token_el_socket_se_cierra() -> None:
    with _client() as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/jobs/{uuid4()}") as socket:
                socket.send_json({"token": "no-es-un-jwt"})
                socket.receive_json()


def test_el_socket_repite_el_estado_y_luego_el_cierre() -> None:
    with _client() as client:
        token = _token(client)
        job = client.portal.call(_pending, client, token)  # type: ignore[attr-defined]
        assert isinstance(job, ScrapeJob)
        bus = client.app.state.events
        assert isinstance(bus, MemoryEventBus)
        with client.websocket_connect(f"/ws/jobs/{job.id}") as socket:
            socket.send_json({"token": token})
            assert socket.receive_json()["status"] == "pending"
            time.sleep(0.05)
            bus.publish_soon(
                job_channel(job.id),
                {"id": str(job.id), "status": "done", "song_id": 3, "error": None},
            )
            done = socket.receive_json()
        assert done["status"] == "done"
        assert done["song_id"] == 3


def test_un_trabajo_ajeno_no_se_escucha() -> None:
    with _client() as client:
        token = _token(client)
        job = client.portal.call(_pending, client, None)
        assert isinstance(job, ScrapeJob)
        owned = ScrapeJob(
            id=job.id,
            user_id=uuid4(),
            song_id=None,
            status="pending",
            query="estudio",
            error=None,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        uow = client.app.state.uow
        assert isinstance(uow, InMemoryUnitOfWork)
        client.portal.call(uow.jobs.add, owned)
        with client.websocket_connect(f"/ws/jobs/{job.id}") as socket:
            socket.send_json({"token": token})
            body = socket.receive_json()
        assert body["error"] == "El trabajo no existe."


async def test_redis_entrega_el_aviso_a_quien_escucha() -> None:
    client = FakeAsyncRedis(decode_responses=True)
    bus = RedisEventBus(client)
    heard: list[dict[str, object]] = []

    async def listen() -> None:
        async for event in bus.subscribe("guitarcoach:job:1"):
            heard.append(event)
            return

    task = asyncio.create_task(listen())
    await asyncio.sleep(0.05)
    await bus.publish(
        "guitarcoach:job:1", {"id": "1", "status": "done", "song_id": 2, "error": None}
    )
    await task
    await bus.aclose()
    assert heard == [{"id": "1", "status": "done", "song_id": 2, "error": None}]
