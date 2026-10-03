"""POST /attempts exige token y devuelve la precisión calculada."""

from app.core.config import Settings
from app.domain.entities.song import ChartChord, Song
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord
from app.main import create_app
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
