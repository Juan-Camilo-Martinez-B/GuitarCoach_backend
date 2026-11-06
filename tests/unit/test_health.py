"""La sonda de vida no depende de la base de datos."""

from app.main import create_app
from app.shared.config import Settings
from fastapi.testclient import TestClient


def test_health_responde_ok() -> None:
    client = TestClient(create_app(Settings(environment="local")))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
