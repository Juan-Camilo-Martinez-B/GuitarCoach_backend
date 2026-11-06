"""La búsqueda devuelve la carta, no solo el título."""

from app.main import create_app
from app.modules.catalog.domain.song import ChartChord, Song
from app.shared.config import Settings
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord
from fastapi.testclient import TestClient


async def test_la_busqueda_incluye_los_acordes() -> None:
    app = create_app(Settings(environment="local"))
    await app.state.uow.songs.add(
        Song(
            title="Muestra",
            artist="Demo",
            song_key="C",
            bpm=Bpm(80),
            chords=(ChartChord(1, 1, Chord.parse("C")), ChartChord(1, 3, Chord.parse("G"))),
            source_url=None,
            source_name=None,
            content_hash="hash-de-prueba",
        )
    )
    response = TestClient(app).get("/songs", params={"q": "Muestra"})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["chords"] == [
        {"bar": 1, "beat": 1.0, "chord": "C"},
        {"bar": 1, "beat": 3.0, "chord": "G"},
    ]
