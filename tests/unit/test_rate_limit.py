"""El límite de autenticación responde 429 sin tocar la base de datos."""

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_el_tercer_login_seguido_queda_bloqueado() -> None:
    client = TestClient(create_app(Settings(environment="local", auth_requests_per_minute=2)))
    body = {"email": "nadie@example.com", "password": "secreto-largo"}
    assert client.post("/auth/login", json=body).status_code == 401
    assert client.post("/auth/login", json=body).status_code == 401
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
