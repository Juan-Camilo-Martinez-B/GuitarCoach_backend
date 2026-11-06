"""Puertos del diario de práctica. La infraestructura los implementa."""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.modules.guides.public import GuideRepository
from app.modules.learning.public import LessonRepository
from app.modules.practice.public import AttemptRepository
from app.shared.persistence.transaction import Transactional


class JourneyRepository(Protocol):
    async def milestones(self, user_id: UUID) -> set[str]: ...

    async def days(self, user_id: UUID) -> set[date]: ...

    async def add_milestones(
        self, user_id: UUID, milestones: Iterable[str], when: datetime
    ) -> None: ...

    async def add_days(self, user_id: UUID, days: Iterable[date]) -> None: ...


class JourneyStore(Transactional, Protocol):
    journey: JourneyRepository
    attempts: AttemptRepository
    guides: GuideRepository
    lessons: LessonRepository
