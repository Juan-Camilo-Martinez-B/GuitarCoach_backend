"""El caso de uso recalcula la precisión y no confía en un porcentaje enviado por el cliente."""

from app.bootstrap.unit_of_work import InMemoryUnitOfWork
from app.modules.catalog.domain.song import ChartChord, Song
from app.modules.practice.application.register_attempt import (
    RegisterAttempt,
    TelemetryEvent,
    hit_window_ms,
)
from app.modules.practice.domain.attempt_assessor import AttemptAssessor
from app.shared.clock import SystemClock
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


async def test_guarda_el_intento_con_la_precision_calculada() -> None:
    uow = InMemoryUnitOfWork()
    song = await uow.songs.add(
        Song(
            title="Progresión",
            artist="Demo",
            song_key="C",
            bpm=Bpm(80),
            chords=(ChartChord(1, 1, Chord.parse("G")), ChartChord(2, 1, Chord.parse("C"))),
            source_url=None,
            source_name=None,
            content_hash="hash-intento",
        )
    )
    assert song.id is not None
    attempt = await RegisterAttempt(uow, AttemptAssessor(), SystemClock(), 150).execute(
        user_id=(await _user(uow)),
        song_id=song.id,
        bpm=80,
        latency_offset_ms=0,
        tuning_cents_avg=-4.0,
        events=(
            TelemetryEvent(1, "G", "G", 30, 0.9),
            TelemetryEvent(2, "C", "Am", 20, 0.4),
        ),
    )
    stored = await uow.attempts.get(attempt.id)
    assert stored is not None
    assert stored.accuracy == 50.0
    metrics = await uow.attempts.metrics_for(attempt.id)
    assert {metric.chord for metric in metrics} == {"C", "G"}


async def _user(uow: InMemoryUnitOfWork):
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.modules.identity.domain.user import User

    user = User(
        id=uuid4(),
        email="intento@example.com",
        display_name="Ana",
        level="beginner",
        password_hash="hash",
        oauth_subject=None,
        latency_offset_ms=0,
        created_at=datetime.now(UTC),
    )
    await uow.users.add(user)
    return user.id


def test_la_ventana_de_acierto_no_pasa_de_medio_tiempo() -> None:
    assert hit_window_ms(150, 72) == 150
    assert hit_window_ms(150, 200) == 150
    assert hit_window_ms(150, 240) == 125
    assert hit_window_ms(150, 300) == 100
