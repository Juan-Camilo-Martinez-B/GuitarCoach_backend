"""Pide un informe, reutiliza la caché por hash y aplica el límite diario."""

import hashlib
import json
from uuid import UUID, uuid4

from app.modules.coaching.application.prompts import PromptBuilder
from app.modules.coaching.domain.report import Report
from app.modules.coaching.domain.training_coach import LOCAL_MODEL, local_report
from app.modules.coaching.ports import CoachingStore, Tutor
from app.shared.clock import Clock
from app.shared.errors import ExternalServiceError, NotFoundError, RateLimitExceededError

# Por debajo de esta precisión un acorde cuenta como débil en el informe.
WEAK_CHORD_ACCURACY = 70.0


class CreateReport:
    def __init__(self, uow: CoachingStore, tutor: Tutor, clock: Clock, daily_limit: int) -> None:
        self._uow = uow
        self._tutor = tutor
        self._clock = clock
        self._daily_limit = daily_limit

    async def _weak_chords(self, attempt_id: UUID) -> tuple[str, ...]:
        metrics = await self._uow.attempts.metrics_for(attempt_id)
        weakest = sorted(metrics, key=lambda item: item.accuracy)
        return tuple(str(item.chord) for item in weakest if item.accuracy < WEAK_CHORD_ACCURACY)

    async def execute(self, user_id: UUID, attempt_id: UUID, level: str) -> Report:
        # Primero la propiedad: un informe ajeno responde igual que uno que no existe.
        attempt = await self._uow.attempts.get(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise NotFoundError("El intento no existe.")
        existing = await self._uow.reports.get_by_attempt(attempt_id)
        if existing is not None:
            return existing
        song = await self._uow.songs.get(attempt.song_id)
        if song is None:
            raise NotFoundError("La canción del intento no existe.")
        metrics_hash = _hash_attempt(attempt.accuracy, attempt.avg_delta_ms, attempt.song_id)
        cached = await self._uow.reports.find_by_metrics_hash(metrics_hash)
        if cached is None:
            used = await self._uow.reports.count_for_user_on_day(user_id, self._clock.now().date())
            if used >= self._daily_limit:
                raise RateLimitExceededError("Llegaste al límite diario de informes.")
            weak = await self._weak_chords(attempt_id)
            model = "tutor"
            try:
                content = await self._tutor.advise(
                    PromptBuilder().build(
                        song.title, level, attempt.accuracy, attempt.avg_delta_ms, weak
                    )
                )
            except ExternalServiceError:
                # Sin tutor externo el alumno igual recibe su informe, calculado con sus datos.
                content = local_report(song.title, attempt.accuracy, attempt.avg_delta_ms, weak)
                model = LOCAL_MODEL
        else:
            content = cached.content
            model = "cache"
        report = Report(
            id=uuid4(),
            attempt_id=attempt_id,
            content=content,
            model=model,
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
