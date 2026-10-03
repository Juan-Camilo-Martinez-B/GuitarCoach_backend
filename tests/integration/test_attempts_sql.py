"""El intento se guarda en PostgreSQL con sus métricas por acorde."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from app.application.security import SystemClock
from app.application.use_cases.register_attempt import RegisterAttempt, TelemetryEvent
from app.domain.entities.song import ChartChord, Song
from app.domain.entities.user import User
from app.domain.services.attempt_assessor import AttemptAssessor
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord
from app.infrastructure.db.models import AttemptModel, ChordMetricModel, SongModel, UserModel
from app.infrastructure.db.repositories import SqlUnitOfWork
from app.infrastructure.db.session import create_engine, create_session_factory
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL no está definida",
)


async def test_el_intento_sobrevive_en_postgres() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    async with factory() as session:
        uow = SqlUnitOfWork(session)
        user = User(
            id=uuid4(),
            email=f"sql-{uuid4().hex[:8]}@example.com",
            display_name="SQL",
            level="beginner",
            password_hash="hash",
            oauth_subject=None,
            latency_offset_ms=0,
            created_at=SystemClock().now(),
        )
        await uow.users.add(user)
        song = await uow.songs.add(
            Song(
                title="SQL",
                artist="Prueba",
                song_key="C",
                bpm=Bpm(80),
                chords=(ChartChord(1, 1, Chord.parse("Am")),),
                source_url=None,
                source_name="test",
                content_hash=f"sql-{uuid4().hex}",
            )
        )
        assert song.id is not None
        attempt = await RegisterAttempt(uow, AttemptAssessor(), SystemClock(), 150).execute(
            user.id,
            song.id,
            80,
            0,
            None,
            (TelemetryEvent(1, "Am", "Am", 25, 0.95),),
        )
        stored = await uow.attempts.get(attempt.id)
        metrics = await uow.attempts.metrics_for(attempt.id)
        assert stored is not None
        assert stored.accuracy == 100.0
        assert metrics[0].chord == "Am"
        await session.execute(
            delete(ChordMetricModel).where(ChordMetricModel.attempt_id == attempt.id)
        )
        await session.execute(delete(AttemptModel).where(AttemptModel.id == attempt.id))
        await session.execute(delete(SongModel).where(SongModel.id == song.id))
        await session.execute(delete(UserModel).where(UserModel.id == user.id))
        await session.commit()
    await engine.dispose()
