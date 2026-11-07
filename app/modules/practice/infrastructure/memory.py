"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from uuid import UUID

from app.modules.practice.domain.attempt import Attempt, ChordMetric


class InMemoryAttempts:
    def __init__(self) -> None:
        self._attempts: dict[UUID, Attempt] = {}
        self._metrics: dict[UUID, tuple[ChordMetric, ...]] = {}

    async def add(self, attempt: Attempt, metrics: tuple[ChordMetric, ...]) -> None:
        self._attempts[attempt.id] = attempt
        self._metrics[attempt.id] = metrics

    async def get(self, attempt_id: UUID) -> Attempt | None:
        return self._attempts.get(attempt_id)

    async def list_for_user(self, user_id: UUID) -> tuple[Attempt, ...]:
        return tuple(item for item in self._attempts.values() if item.user_id == user_id)

    async def metrics_for(self, attempt_id: UUID) -> tuple[ChordMetric, ...]:
        return self._metrics.get(attempt_id, ())

    async def delete(self, attempt_id: UUID) -> None:
        self._attempts.pop(attempt_id, None)
        self._metrics.pop(attempt_id, None)
