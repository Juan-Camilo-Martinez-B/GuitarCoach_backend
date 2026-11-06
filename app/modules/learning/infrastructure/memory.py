"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from datetime import date, datetime
from uuid import UUID


class InMemoryLessons:
    def __init__(self) -> None:
        self._done: dict[tuple[UUID, str], datetime] = {}
        self._reviews: set[tuple[UUID, date]] = set()

    async def completed(self, user_id: UUID) -> dict[str, datetime]:
        return {
            lesson_id: when for (owner, lesson_id), when in self._done.items() if owner == user_id
        }

    async def mark_completed(self, user_id: UUID, lesson_id: str, when: datetime) -> None:
        self._done[(user_id, lesson_id)] = when

    async def reviewed_on(self, user_id: UUID, day: date) -> bool:
        return (user_id, day) in self._reviews

    async def mark_reviewed(self, user_id: UUID, day: date) -> None:
        self._reviews.add((user_id, day))
