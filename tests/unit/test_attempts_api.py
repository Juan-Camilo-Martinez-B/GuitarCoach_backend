"""POST /attempts exige token y devuelve la precisión calculada."""

from app.main import create_app
from app.modules.catalog.domain.song import ChartChord, Song
from app.shared.config import Settings
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord
from fastapi.testclient import TestClient

SECRET = "secreto-de-prueba-con-longitud-suficiente"


def test_post_attempts_persiste_en_el_almacen_de_la_app() -> None:
    app = create_app(Settings(environment="local", jwt_secret=SECRET))
    client = TestClient(app)
    client.post(
        "/auth/register",
        json={"email": "api@example.com", "password": "secreto-largo", "display_name": "Ana"},
    )
    token = client.post(
        "/auth/login",
        json={"email": "api@example.com", "password": "secreto-largo"},
    ).json()["access_token"]

    import anyio

    async def add_song() -> int:
        song = await app.state.uow.songs.add(
            Song(
                title="API",
                artist="Demo",
                song_key="G",
                bpm=Bpm(80),
                chords=(ChartChord(1, 1, Chord.parse("G")),),
                source_url=None,
                source_name=None,
                content_hash="hash-api",
            )
        )
        assert song.id is not None
        return song.id

    song_id = anyio.run(add_song)
    response = client.post(
        "/attempts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "song_id": song_id,
            "bpm": 80,
            "events": [
                {"bar": 1, "expected": "G", "detected": "G", "delta_ms": 20, "confidence": 0.8}
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["accuracy"] == 100.0


def test_borrar_un_intento_quita_su_informe_y_no_toca_el_ajeno() -> None:
    app = create_app(Settings(environment="local", jwt_secret=SECRET))
    client = TestClient(app)

    def token_for(email: str) -> str:
        body = {"email": email, "password": "secreto-largo", "display_name": "Ana"}
        assert client.post("/auth/register", json=body).status_code == 201
        return client.post("/auth/login", json=body).json()["access_token"]

    owner = token_for("borra@example.com")
    other = token_for("otro@example.com")

    import anyio

    async def add_song() -> int:
        song = await app.state.uow.songs.add(
            Song(
                title="Para borrar",
                artist="Demo",
                song_key="G",
                bpm=Bpm(72),
                chords=(ChartChord(1, 1, Chord.parse("G")),),
                source_url=None,
                source_name=None,
                content_hash="hash-borrar",
            )
        )
        assert song.id is not None
        return song.id

    song_id = anyio.run(add_song)
    created = client.post(
        "/attempts",
        headers={"Authorization": f"Bearer {owner}"},
        json={
            "song_id": song_id,
            "bpm": 72,
            "events": [
                {"bar": 1, "expected": "G", "detected": "G", "delta_ms": 10, "confidence": 0.9}
            ],
        },
    )
    assert created.status_code == 201
    attempt_id = created.json()["id"]
    report = client.post(
        f"/attempts/{attempt_id}/report",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert report.status_code == 201
    denied = client.delete(
        f"/attempts/{attempt_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert denied.status_code == 404
    removed = client.delete(
        f"/attempts/{attempt_id}",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert removed.status_code == 204
    gone = client.get(
        f"/attempts/{attempt_id}/report",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert gone.status_code == 404
    progress = client.get("/me/progress", headers={"Authorization": f"Bearer {owner}"}).json()
    assert progress == []
