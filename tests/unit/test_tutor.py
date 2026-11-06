"""El informe usa un doble del modelo y no llama a Groq."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.bootstrap.unit_of_work import InMemoryUnitOfWork
from app.modules.catalog.domain.song import ChartChord, Song
from app.modules.coaching.application.create_report import CreateReport
from app.modules.coaching.application.prompts import PromptBuilder
from app.modules.coaching.domain.report import ReportContent
from app.modules.coaching.infrastructure.groq_tutor import GroqTutor
from app.modules.coaching.infrastructure.tutor import ReportDraft
from app.modules.identity.domain.user import User
from app.modules.practice.domain.attempt import Attempt
from app.modules.practice.domain.hit_result import HitKind, HitResult
from app.shared.errors import ExternalServiceError, RateLimitExceededError
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 10, 3, tzinfo=UTC)


class FakeTutor:
    def __init__(self) -> None:
        self.calls = 0

    async def advise(self, prompt: str) -> ReportContent:
        self.calls += 1
        assert "METRICAS" in prompt
        return ReportDraft(
            diagnostico="El cambio a C llega tarde.",
            ejercicios=["G a C a 60 BPM."],
            plan_semanal=["Dia 1: metrónomo."],
            consejos_tecnica=["Prepara el dedo 1."],
        ).to_content()


async def test_el_segundo_informe_igual_no_vuelve_a_llamar_al_modelo() -> None:
    uow = InMemoryUnitOfWork()
    user_id = await _user(uow)
    song = await _song(uow)
    assert song.id is not None
    first_attempt = await _attempt(uow, user_id, song.id)
    second_attempt = await _attempt(uow, user_id, song.id)
    tutor = FakeTutor()
    use_case = CreateReport(uow, tutor, FixedClock(), daily_limit=5)
    first = await use_case.execute(user_id, first_attempt, "beginner")
    second = await use_case.execute(user_id, second_attempt, "beginner")
    assert tutor.calls == 1
    assert second.content.diagnostico == first.content.diagnostico
    assert second.model == "cache"


async def test_el_limite_diario_cuenta_informes_con_metricas_distintas() -> None:
    uow = InMemoryUnitOfWork()
    user_id = await _user(uow)
    song = await _song(uow)
    assert song.id is not None
    first = await _attempt(uow, user_id, song.id, accuracy=40)
    second = await _attempt(uow, user_id, song.id, accuracy=10)
    use_case = CreateReport(uow, FakeTutor(), FixedClock(), daily_limit=1)
    await use_case.execute(user_id, first, "beginner")
    with pytest.raises(RateLimitExceededError):
        await use_case.execute(user_id, second, "beginner")


async def test_el_limite_diario_bloquea_un_informe_nuevo() -> None:
    uow = InMemoryUnitOfWork()
    user_id = await _user(uow)
    song = await _song(uow)
    assert song.id is not None
    attempt_id = await _attempt(uow, user_id, song.id)
    use_case = CreateReport(uow, FakeTutor(), FixedClock(), daily_limit=0)
    with pytest.raises(RateLimitExceededError):
        await use_case.execute(user_id, attempt_id, "beginner")


async def test_groq_sin_clave_no_llama_a_la_red() -> None:
    tutor = GroqTutor("  ", "llama-3.3-70b-versatile")
    with pytest.raises(ExternalServiceError, match="GROQ_API_KEY"):
        await tutor.advise("METRICAS")


async def test_groq_rechaza_una_respuesta_que_no_es_json() -> None:
    tutor = GroqTutor("clave-de-prueba", "llama-3.3-70b-versatile")

    async def _invalid(_prompt: str) -> str:
        return "esto no es json"

    tutor._complete = _invalid  # type: ignore[method-assign]
    with pytest.raises(ExternalServiceError):
        await tutor.advise("METRICAS")


def test_el_prompt_no_mezcla_instrucciones_con_las_metricas() -> None:
    prompt = PromptBuilder().build("Canción", "beginner", 40, 120, ("C",))
    assert "No inventes cifras" in prompt
    assert '"acordes_debiles": ["C"]' in prompt


async def _user(uow: InMemoryUnitOfWork):
    user = User(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@example.com",
        display_name="Ana",
        level="beginner",
        password_hash="hash",
        oauth_subject=None,
        latency_offset_ms=0,
        created_at=datetime.now(UTC),
    )
    await uow.users.add(user)
    return user.id


async def _song(uow: InMemoryUnitOfWork) -> Song:
    return await uow.songs.add(
        Song(
            title="Canción",
            artist="Demo",
            song_key="C",
            bpm=Bpm(80),
            chords=(ChartChord(1, 1, Chord.parse("C")),),
            source_url=None,
            source_name=None,
            content_hash=uuid4().hex,
        )
    )


async def _attempt(uow: InMemoryUnitOfWork, user_id, song_id: int, accuracy: float = 40):
    attempt = Attempt(
        id=uuid4(),
        user_id=user_id,
        song_id=song_id,
        bpm=Bpm(80),
        accuracy=accuracy,
        avg_delta_ms=120,
        latency_offset_ms=0,
        tuning_cents_avg=None,
        events=(
            HitResult(
                expected=Chord.parse("C"),
                detected=Chord.parse("G"),
                delta_ms=120,
                kind=HitKind.MISS,
            ),
        ),
        created_at=datetime.now(UTC),
    )
    await uow.attempts.add(attempt, ())
    return attempt.id
