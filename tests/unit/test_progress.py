"""El historial dice qué canción se practicó en cada intento."""

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_el_progreso_incluye_el_titulo_de_la_cancion() -> None:
    with TestClient(
        create_app(Settings(environment="local", auth_requests_per_minute=50))
    ) as client:
        body = {"email": "progreso@example.com", "password": "secreto-largo", "display_name": "Ana"}
        assert client.post("/auth/register", json=body).status_code == 201
        token = client.post("/auth/login", json=body).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        song = client.get("/songs", params={"q": "Cambios abiertos"}).json()[0]
        attempt = {
            "song_id": song["id"],
            "bpm": song["bpm"],
            "events": [
                {"bar": 1, "expected": "G", "detected": "G", "delta_ms": 20, "confidence": 0.9}
            ],
        }
        assert client.post("/attempts", json=attempt, headers=headers).status_code == 201
        points = client.get("/me/progress", headers=headers).json()
        assert points[0]["song_title"] == "Cambios abiertos"
