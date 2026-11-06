"""Registra un intento a partir de la telemetría. El servidor recalcula la precisión."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.practice.domain.attempt import Attempt, ChordMetric
from app.modules.practice.domain.attempt_assessor import AttemptAssessor
from app.modules.practice.domain.hit_result import HitResult
from app.modules.practice.ports import PracticeStore
from app.shared.clock import Clock
from app.shared.errors import NotFoundError
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


def hit_window_ms(window_ms: int, bpm: int) -> int:
    """A tempos altos un tiempo dura menos que la ventana: nunca abarca más de medio tiempo."""
    half_beat = 30_000 // bpm
    return min(window_ms, half_beat)


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    bar: int
    expected: str
    detected: str | None
    delta_ms: int
    confidence: float


class RegisterAttempt:
    def __init__(
        self,
        uow: PracticeStore,
        assessor: AttemptAssessor,
        clock: Clock,
        window_ms: int,
    ) -> None:
        self._uow = uow
        self._assessor = assessor
        self._clock = clock
        self._window_ms = window_ms

    async def execute(
        self,
        user_id: UUID,
        song_id: int,
        bpm: int,
        latency_offset_ms: int,
        tuning_cents_avg: float | None,
        events: tuple[TelemetryEvent, ...],
    ) -> Attempt:
        song = await self._uow.songs.get(song_id)
        if song is None:
            raise NotFoundError("La canción no existe.")
        window = hit_window_ms(self._window_ms, Bpm(bpm).value)
        judged = tuple(self._judge(event, window) for event in events)
        assessment = self._assessor.assess(judged)
        attempt = Attempt(
            id=uuid4(),
            user_id=user_id,
            song_id=song_id,
            bpm=Bpm(bpm),
            accuracy=assessment.accuracy,
            avg_delta_ms=assessment.avg_delta_ms,
            latency_offset_ms=latency_offset_ms,
            tuning_cents_avg=tuning_cents_avg,
            events=judged,
            created_at=self._clock.now(),
        )
        metrics = tuple(
            ChordMetric(
                chord=item.chord,
                accuracy=item.accuracy,
                avg_delta_ms=item.avg_delta_ms,
                errors=item.errors,
            )
            for item in assessment.chord_metrics
        )
        await self._uow.attempts.add(attempt, metrics)
        await self._uow.commit()
        return attempt

    def _judge(self, event: TelemetryEvent, window_ms: int) -> HitResult:
        detected = Chord.parse(event.detected) if event.detected else None
        judged = HitResult.judge(
            Chord.parse(event.expected),
            detected,
            event.delta_ms,
            window_ms,
        )
        return HitResult(
            expected=judged.expected,
            detected=judged.detected,
            delta_ms=judged.delta_ms,
            kind=judged.kind,
            bar=event.bar,
            confidence=event.confidence,
        )
