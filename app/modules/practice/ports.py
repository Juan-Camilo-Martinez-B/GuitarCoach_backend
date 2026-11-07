"""Puertos de la práctica. La infraestructura los implementa."""

from typing import Protocol
from uuid import UUID

from app.modules.catalog.public import SongRepository
from app.modules.practice.domain.attempt import Attempt, ChordMetric
from app.shared.persistence.transaction import Transactional


class AttemptRepository(Protocol):
    async def add(self, attempt: Attempt, metrics: tuple[ChordMetric, ...]) -> None: ...

    async def get(self, attempt_id: UUID) -> Attempt | None: ...

    async def list_for_user(self, user_id: UUID) -> tuple[Attempt, ...]: ...

    async def metrics_for(self, attempt_id: UUID) -> tuple[ChordMetric, ...]: ...

    async def delete(self, attempt_id: UUID) -> None: ...


class PracticeStore(Transactional, Protocol):
    attempts: AttemptRepository
    songs: SongRepository
