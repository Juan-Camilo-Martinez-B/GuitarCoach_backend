"""Un audio sintético con acordes conocidos sale como guía con esos acordes y su tempo."""

import io

import pytest
from app.domain.errors import InvalidValueError

np = pytest.importorskip("numpy")
pytest.importorskip("librosa")
soundfile = pytest.importorskip("soundfile")

from app.core.config import Settings  # noqa: E402
from app.infrastructure.audio.analysis import analyze_bytes, sniff_audio  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

RATE = 22050
SHAPES = {
    "G": [43, 47, 50, 55, 59, 67],
    "D": [50, 57, 62, 66],
    "Em": [40, 47, 52, 55, 59, 64],
    "C": [48, 52, 55, 60, 64],
}


def _strummed(progression: list[str], bpm: int = 120, beats_each: int = 4) -> bytes:
    """Cada pulso es un rasgueo: las cuerdas del acorde con armónicos y caída exponencial."""
    beat = 60 / bpm
    length = int(RATE * beat * beats_each * len(progression)) + RATE
    signal = np.zeros(length)
    shape_time = np.arange(int(RATE * beat)) / RATE
    envelope = np.exp(-shape_time * 6)
    for index, symbol in enumerate(progression):
        for hit in range(beats_each):
            start = int(RATE * beat * (index * beats_each + hit))
            for midi in SHAPES[symbol]:
                frequency = 440 * 2 ** ((midi - 69) / 12)
                tone = sum(
                    np.sin(2 * np.pi * frequency * harmonic * shape_time) / harmonic
                    for harmonic in range(1, 5)
                )
                signal[start : start + shape_time.size] += 0.04 * tone * envelope
    buffer = io.BytesIO()
    soundfile.write(buffer, signal.astype("float32"), RATE, format="WAV")
    return buffer.getvalue()


def _sequence(symbols: list[str]) -> list[str]:
    merged: list[str] = []
    for symbol in symbols:
        if not merged or merged[-1] != symbol:
            merged.append(symbol)
    return merged


def test_reconoce_la_progresion_y_el_tempo() -> None:
    analysis = analyze_bytes(_strummed(["G", "D", "Em", "C", "G", "D", "Em", "C"]))
    assert 110 <= analysis.bpm <= 130
    found = _sequence([chord.symbol for chord in analysis.chords])
    assert found[:4] == ["G", "D", "Em", "C"]
    # Cada acorde dura cerca de un compás de cuatro pulsos.
    assert 3 <= analysis.chords[1].beats <= 5


def test_reconoce_el_formato_por_su_contenido() -> None:
    assert sniff_audio(_strummed(["G"])) == ".wav"
    assert sniff_audio(b"ID3\x04rest") == ".mp3"
    assert sniff_audio(b"OggS....") == ".ogg"
    assert sniff_audio(b"<html>no soy audio</html>") is None
    with pytest.raises(InvalidValueError):
        analyze_bytes(b"texto que dice ser un mp3")


def test_rechaza_el_silencio() -> None:
    buffer = io.BytesIO()
    soundfile.write(buffer, np.zeros(RATE * 5, dtype="float32"), RATE, format="WAV")
    with pytest.raises(InvalidValueError):
        analyze_bytes(buffer.getvalue())


def test_el_endpoint_crea_una_guia_en_borrador_y_limita_por_dia() -> None:
    settings = Settings(environment="local", auth_requests_per_minute=50, daily_audio_limit=1)
    with TestClient(create_app(settings)) as client:
        body = {"email": "audio@example.com", "password": "secreto-largo", "display_name": "Ana"}
        assert client.post("/auth/register", json=body).status_code == 201
        token = client.post("/auth/login", json=body).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        audio = _strummed(["G", "D", "Em", "C", "G", "D"])
        form = {"title": "Mi grabación", "artist": "Ana"}
        files = {"file": ("toma.wav", audio, "audio/wav")}
        response = client.post("/guides/from-audio", data=form, files=files, headers=headers)
        assert response.status_code == 201
        guide = response.json()
        assert guide["source_kind"] == "audio"
        assert guide["status"] == "borrador"
        assert guide["guide"]["sections"][0]["name"] == "Parte 1"
        second = client.post("/guides/from-audio", data=form, files=files, headers=headers)
        assert second.status_code == 429
