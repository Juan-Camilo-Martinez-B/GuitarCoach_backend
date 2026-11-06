"""El monolito completo contra los servicios reales: PostgreSQL y Redis."""

from __future__ import annotations

import json
import os
import time
from uuid import uuid4

import pytest
import redis
from app.main import create_app
from app.shared.clock import SystemClock
from app.shared.config import Settings
from fastapi.testclient import TestClient

SECRET = "secreto-de-prueba-con-longitud-suficiente"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
REDIS_URL = os.environ.get("TEST_REDIS_URL", "")


def _settings(**extra: object) -> Settings:
    return Settings(jwt_secret=SECRET, groq_api_key="", _env_file=None, **extra)


def _headers(client: TestClient) -> dict[str, str]:
    email = f"vivo-{uuid4().hex[:10]}@example.com"
    created = client.post(
        "/auth/register",
        json={"email": email, "password": "secreto-largo", "display_name": "Ana"},
    )
    assert created.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": "secreto-largo"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL no está definida")
def test_el_diario_sobrevive_en_postgres_y_no_duplica() -> None:
    today = SystemClock().now().date().isoformat()
    settings = _settings(use_database=True, database_url=DATABASE_URL, redis_url="")
    with TestClient(create_app(settings)) as client:
        headers = _headers(client)
        body = {"today": today, "milestones": ["afinar"], "days": [today]}
        assert client.post("/me/journey", json=body, headers=headers).status_code == 200
        again = client.post("/me/journey", json=body, headers=headers)
        assert again.status_code == 200
        assert again.json()["milestones"] == ["afinar"]
        assert again.json()["days"] == [today]
    # Otro proceso, misma base: sigue ahí.
    with TestClient(create_app(settings)) as client:
        assert client.get("/songs", params={"q": "Cambios"}).status_code == 200


@pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL no está definida")
def test_el_trabajo_avisa_por_redis_y_el_socket_lo_entrega() -> None:
    listener = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = listener.pubsub()
    pubsub.psubscribe("guitarcoach:job:*")
    settings = _settings(use_database=False, redis_url=REDIS_URL)
    try:
        with TestClient(create_app(settings)) as client:
            assert type(client.app.state.events).__name__ == "RedisEventBus"  # type: ignore[attr-defined]
            headers = _headers(client)
            job = client.post("/songs/import", json={"query": "muestra"}).json()

            published: dict[str, object] | None = None
            deadline = time.monotonic() + 5
            while published is None and time.monotonic() < deadline:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
                if message and message["channel"] == f"guitarcoach:job:{job['id']}":
                    published = json.loads(message["data"])
            assert published is not None, "Redis no recibió el aviso del trabajo."
            assert published["status"] == "done"

            with client.websocket_connect(f"/ws/jobs/{job['id']}") as socket:
                token = headers["Authorization"].removeprefix("Bearer ")
                socket.send_text(json.dumps({"token": token}))
                assert socket.receive_json()["status"] == "done"
    finally:
        pubsub.close()
        listener.close()
