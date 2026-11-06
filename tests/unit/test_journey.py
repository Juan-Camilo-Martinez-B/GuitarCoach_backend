"""La ruta y los logros se guardan en la cuenta, también lo que ya demuestran otros módulos."""

from datetime import date, timedelta

from app.main import create_app
from app.modules.journey.domain.journey import earned_badges, snapshot, streaks
from app.shared.clock import SystemClock
from app.shared.config import Settings
from fastapi.testclient import TestClient

SECRET = "secreto-de-prueba-con-longitud-suficiente"
TODAY = SystemClock().now().date()


def _client() -> TestClient:
    return TestClient(create_app(Settings(jwt_secret=SECRET, redis_url="", groq_api_key="")))


def _headers(client: TestClient, email: str = "ana@example.com") -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "secreto-largo", "display_name": "Ana"},
    )
    login = client.post("/auth/login", json={"email": email, "password": "secreto-largo"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_la_racha_cuenta_dias_seguidos_y_se_pierde_tras_un_hueco() -> None:
    day = date(2026, 3, 10)
    days = [day - timedelta(days=offset) for offset in (0, 1, 2, 5)]
    assert streaks(days, day) == (3, 3)
    assert streaks(days, day + timedelta(days=1)) == (3, 3)
    assert streaks(days, day + timedelta(days=2)) == (0, 3)
    assert streaks([], day) == (0, 0)


def test_los_logros_salen_de_los_pasos_y_de_la_mejor_racha() -> None:
    assert earned_badges(["afinar"], 1) == ("buen-oido",)
    assert "tres-dias" in earned_badges([], 3)
    every = ("afinar", "acorde", "tocar", "propia", "avance")
    assert "ruta-completa" in earned_badges(every, 0)
    assert snapshot(["avance", "afinar"], [], date(2026, 3, 10)).milestones == ("afinar", "avance")


def test_sin_token_no_hay_diario() -> None:
    with _client() as client:
        assert client.get("/me/journey", params={"today": TODAY.isoformat()}).status_code == 422
        rejected = client.get(
            "/me/journey",
            params={"today": TODAY.isoformat()},
            headers={"Authorization": "Bearer mal"},
        )
        assert rejected.status_code == 401


def test_guardar_es_idempotente_y_cada_cuenta_ve_lo_suyo() -> None:
    with _client() as client:
        ana = _headers(client)
        body = {
            "today": TODAY.isoformat(),
            "milestones": ["afinar"],
            "days": [TODAY.isoformat(), (TODAY - timedelta(days=1)).isoformat()],
        }
        first = client.post("/me/journey", json=body, headers=ana)
        again = client.post("/me/journey", json=body, headers=ana)
        assert first.status_code == 200
        assert first.json() == again.json()
        assert first.json()["current_streak"] == 2
        assert first.json()["badges"] == ["buen-oido"]

        leo = _headers(client, "leo@example.com")
        other = client.get("/me/journey", params={"today": TODAY.isoformat()}, headers=leo)
        assert other.json()["milestones"] == []
        assert other.json()["current_streak"] == 0


def test_rechaza_pasos_desconocidos_y_descarta_dias_imposibles() -> None:
    with _client() as client:
        headers = _headers(client)
        unknown = client.post(
            "/me/journey",
            json={"today": TODAY.isoformat(), "milestones": ["trampa"]},
            headers=headers,
        )
        assert unknown.status_code == 422
        future = client.post(
            "/me/journey",
            json={
                "today": (TODAY + timedelta(days=30)).isoformat(),
                "days": [(TODAY + timedelta(days=30)).isoformat(), "2001-01-01"],
            },
            headers=headers,
        )
        assert future.status_code == 200
        assert future.json()["days"] == []


def test_un_intento_guardado_cumple_el_paso_de_tocar_sin_avisar_nada() -> None:
    with _client() as client:
        headers = _headers(client)
        song = client.get("/songs", params={"q": "Cambios"}).json()[0]
        attempt = client.post(
            "/attempts",
            json={
                "song_id": song["id"],
                "bpm": 72,
                "events": [
                    {"bar": 1, "expected": "G", "detected": "G", "delta_ms": 0, "confidence": 0.9}
                ],
            },
            headers=headers,
        )
        assert attempt.status_code == 201
        state = client.get("/me/journey", params={"today": TODAY.isoformat()}, headers=headers)
        assert "tocar" in state.json()["milestones"]
        assert "primera-cancion" in state.json()["badges"]
        assert state.json()["current_streak"] == 1


def test_el_informe_funciona_sin_tutor_externo_y_es_solo_del_dueno() -> None:
    with _client() as client:
        ana = _headers(client)
        song = client.get("/songs", params={"q": "Cambios"}).json()[0]
        attempt = client.post(
            "/attempts",
            json={
                "song_id": song["id"],
                "bpm": 72,
                "events": [
                    {"bar": 1, "expected": "G", "detected": "C", "delta_ms": 40, "confidence": 0.9}
                ],
            },
            headers=ana,
        ).json()
        report = client.post(f"/attempts/{attempt['id']}/report", headers=ana)
        assert report.status_code == 201
        assert report.json()["model"] == "analisis-local"
        assert "Cambios abiertos" in report.json()["diagnostico"]
        assert any("G" in item for item in report.json()["ejercicios"])

        leo = _headers(client, "leo@example.com")
        assert client.post(f"/attempts/{attempt['id']}/report", headers=leo).status_code == 404
        assert client.get(f"/attempts/{attempt['id']}/report", headers=leo).status_code == 404
        assert client.get(f"/attempts/{attempt['id']}/report", headers=ana).status_code == 200
