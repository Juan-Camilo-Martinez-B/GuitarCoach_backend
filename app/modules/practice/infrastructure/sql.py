"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.practice.domain.attempt import Attempt, ChordMetric
from app.modules.practice.domain.hit_result import HitResult
from app.modules.practice.infrastructure.models import AttemptModel, ChordMetricModel
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


def _events_from_summary(raw: dict[str, object]) -> tuple[HitResult, ...]:
    payload = raw.get("events", [])
    if not isinstance(payload, list):
        return ()
    events: list[HitResult] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        detected_raw = item.get("detected")
        detected = Chord.parse(str(detected_raw)) if isinstance(detected_raw, str) else None
        judged = HitResult.judge(
            Chord.parse(str(item["expected"])),
            detected,
            int(item["delta_ms"]),
        )
        events.append(
            HitResult(
                expected=judged.expected,
                detected=judged.detected,
                delta_ms=judged.delta_ms,
                kind=judged.kind,
                bar=int(item.get("bar", 1)),
                confidence=float(item.get("confidence", 1)),
            )
        )
    return tuple(events)


class SqlAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: Attempt, metrics: tuple[ChordMetric, ...]) -> None:
        self._session.add(
            AttemptModel(
                id=attempt.id,
                user_id=attempt.user_id,
                song_id=attempt.song_id,
                bpm=attempt.bpm.value,
                accuracy=attempt.accuracy,
                avg_delta_ms=attempt.avg_delta_ms,
                latency_offset_ms=attempt.latency_offset_ms,
                tuning_cents_avg=attempt.tuning_cents_avg,
                raw_summary={
                    "events": [
                        {
                            "bar": event.bar,
                            "expected": event.expected.symbol,
                            "detected": None if event.detected is None else event.detected.symbol,
                            "delta_ms": event.delta_ms,
                            "confidence": event.confidence,
                            "kind": event.kind.value,
                        }
                        for event in attempt.events
                    ]
                },
                created_at=attempt.created_at,
            )
        )
        for metric in metrics:
            self._session.add(
                ChordMetricModel(
                    attempt_id=attempt.id,
                    chord=metric.chord,
                    accuracy=metric.accuracy,
                    avg_delta_ms=metric.avg_delta_ms,
                    errors=metric.errors,
                )
            )

    async def get(self, attempt_id: UUID) -> Attempt | None:
        row = await self._session.get(AttemptModel, attempt_id)
        return None if row is None else _attempt_to_entity(row)

    async def list_for_user(self, user_id: UUID) -> tuple[Attempt, ...]:
        rows = await self._session.scalars(
            select(AttemptModel).where(AttemptModel.user_id == user_id)
        )
        return tuple(_attempt_to_entity(row) for row in rows)

    async def metrics_for(self, attempt_id: UUID) -> tuple[ChordMetric, ...]:
        rows = await self._session.scalars(
            select(ChordMetricModel).where(ChordMetricModel.attempt_id == attempt_id)
        )
        return tuple(
            ChordMetric(
                chord=row.chord,
                accuracy=float(row.accuracy),
                avg_delta_ms=float(row.avg_delta_ms),
                errors=row.errors,
                id=row.id,
            )
            for row in rows
        )

    async def delete(self, attempt_id: UUID) -> None:
        await self._session.execute(
            delete(ChordMetricModel).where(ChordMetricModel.attempt_id == attempt_id)
        )
        row = await self._session.get(AttemptModel, attempt_id)
        if row is not None:
            await self._session.delete(row)
        await self._session.flush()


def _attempt_to_entity(row: AttemptModel) -> Attempt:
    return Attempt(
        id=row.id,
        user_id=row.user_id,
        song_id=row.song_id,
        bpm=Bpm(row.bpm),
        accuracy=float(row.accuracy),
        avg_delta_ms=float(row.avg_delta_ms),
        latency_offset_ms=row.latency_offset_ms,
        tuning_cents_avg=None if row.tuning_cents_avg is None else float(row.tuning_cents_avg),
        events=_events_from_summary(row.raw_summary),
        created_at=row.created_at,
    )
