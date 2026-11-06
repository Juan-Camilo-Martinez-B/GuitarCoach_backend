"""Puertos del curso. La infraestructura los implementa."""

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.shared.persistence.transaction import Transactional


class LessonRepository(Protocol):
    async def completed(self, user_id: UUID) -> dict[str, datetime]: ...

    async def mark_completed(self, user_id: UUID, lesson_id: str, when: datetime) -> None: ...

    async def reviewed_on(self, user_id: UUID, day: date) -> bool: ...

    async def mark_reviewed(self, user_id: UUID, day: date) -> None: ...


class LearningStore(Transactional, Protocol):
    lessons: LessonRepository
