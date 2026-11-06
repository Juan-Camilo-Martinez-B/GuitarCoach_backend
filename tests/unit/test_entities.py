"""Invariantes de las entidades."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.catalog.domain.scrape_job import ScrapeJob
from app.modules.catalog.domain.song import ChartChord, Song
from app.modules.identity.domain.user import User
from app.shared.errors import InvalidValueError
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


def test_el_usuario_exige_un_metodo_de_acceso() -> None:
    with pytest.raises(InvalidValueError):
        User(
            id=uuid4(),
            email="no-es-correo",
            display_name="Ana",
            level="beginner",
            password_hash=None,
            oauth_subject=None,
            latency_offset_ms=0,
            created_at=datetime.now(UTC),
        )


def test_la_cancion_exige_acordes() -> None:
    with pytest.raises(InvalidValueError):
        Song(
            title="Vacia",
            artist="Nadie",
            song_key="C",
            bpm=Bpm(80),
            chords=(),
            source_url=None,
            source_name=None,
            content_hash="hash",
        )


def test_un_trabajo_fallido_guarda_el_motivo_y_otro_estado_avanza() -> None:
    now = datetime.now(UTC)
    job = ScrapeJob(
        id=uuid4(),
        user_id=None,
        song_id=None,
        status="pending",
        query="am",
        error=None,
        created_at=now,
        updated_at=now,
    )
    done = job.mark_running(now).mark_done(song_id=3, now=now)
    assert done.status == "done"
    assert done.song_id == 3
    with pytest.raises(InvalidValueError):
        job.mark_failed("  ", now)
    assert ChartChord(bar=1, beat=1, chord=Chord.parse("C")).chord.symbol == "C"
