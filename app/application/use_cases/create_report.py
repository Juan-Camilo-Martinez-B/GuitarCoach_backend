"""Pide un informe, reutiliza la caché por hash y aplica el límite diario."""

import hashlib
import json
from uuid import UUID, uuid4

from app.application.security import Clock
from app.domain.entities.report import Report, ReportContent
from app.domain.errors import NotFoundError, RateLimitExceededError
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.ai.tutor import Tutor


class CreateReport:
    def __init__(self, uow: UnitOfWork, tutor: Tutor, clock: Clock, daily_limit: int) -> None:
        self._uow = uow
        self._tutor = tutor
        self._clock = clock
        self._daily_limit = daily_limit

    async def execute(self, user_id: UUID, attempt_id: UUID, level: str) -> Report:
        existing = await self._uow.reports.get_by_attempt(attempt_id)
        if existing is not None:
            return existing
        attempt = await self._uow.attempts.get(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise NotFoundError("El intento no existe.")
        song = await self._uow.songs.get(attempt.song_id)
        if song is None:
            raise NotFoundError("La canción del intento no existe.")
        metrics_hash = _hash_attempt(attempt.accuracy, attempt.avg_delta_ms, attempt.song_id)
        cached = await self._uow.reports.find_by_metrics_hash(metrics_hash)
        if cached is None:
            used = await self._uow.reports.count_for_user_on_day(user_id, self._clock.now().date())
            if used >= self._daily_limit:
                raise RateLimitExceededError("Llegaste al límite diario de informes.")
            content = await self._tutor.advise(
                _prompt(song.title, level, attempt.accuracy, attempt.avg_delta_ms)
            )
        else:
            content = cached.content
        report = Report(
            id=uuid4(),
            attempt_id=attempt_id,
            content=content,
            model="cache" if cached is not None else "tutor",
            metrics_hash=metrics_hash,
            created_at=self._clock.now(),
        )
        await self._uow.reports.add(report)
        await self._uow.commit()
        return report


def _hash_attempt(accuracy: float, avg_delta_ms: float, song_id: int) -> str:
    payload = json.dumps(
        {"accuracy": accuracy, "avg_delta_ms": avg_delta_ms, "song_id": song_id},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _prompt(title: str, level: str, accuracy: float, avg_delta_ms: float) -> str:
    from app.infrastructure.ai.tutor import PromptBuilder

    return PromptBuilder().build(title, level, accuracy, avg_delta_ms, ())


def content_from_tutor(content: ReportContent) -> ReportContent:
    return content
