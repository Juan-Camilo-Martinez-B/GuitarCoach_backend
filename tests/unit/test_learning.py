"""El curso se guarda y un archivo ChordPro produce las dos formas de estudio."""

from app.core.config import Settings
from app.domain.services.chart_import import parse_chart
from app.main import create_app
from fastapi.testclient import TestClient

CHART = """title: Patio
artist: Ana
bpm: 90
key: G
[G] [D] [Em] [C]
melody: G D E C
"""


def test_un_chordpro_separa_acordes_y_melodia() -> None:
    chart = parse_chart("patio.cho", CHART.encode())
    assert chart.title == "Patio"
    assert chart.chords[0] == (1, 1.0, "G")
    assert chart.melody[2] == (1, 3.0, "E")


def test_el_curso_bloquea_el_modulo_siguiente_y_arma_un_quiz() -> None:
    app = create_app(Settings(environment="local", auth_requests_per_minute=50))
    with TestClient(app) as client:
        body = {"email": "curso@example.com", "password": "secreto-largo", "display_name": "Curso"}
        assert client.post("/auth/register", json=body).status_code == 201
        token = client.post("/auth/login", json=body).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        course = client.get("/me/curriculum", headers=headers)
        assert course.status_code == 200
        lessons = course.json()["lessons"]
        assert lessons[0]["locked"] is False
        assert lessons[1]["locked"] is True
        assert client.post("/me/lessons/cuerdas/complete", headers=headers).status_code == 200
        assert client.post("/me/lessons/acorde/complete", headers=headers).status_code == 409
        coach = client.post("/me/coach", headers=headers, json={"mode": "quiz"})
        assert coach.status_code == 200
        assert coach.json()["model"] == "analisis-local"
        uploaded = client.post(
            "/songs/upload",
            headers=headers,
            files={"file": ("patio.cho", CHART.encode(), "text/plain")},
        )
        assert uploaded.status_code == 201
        study = uploaded.json()["study"]
        assert study["difficulty"] == "facil"
        assert study["melody"][0]["label"] == "Sol"
