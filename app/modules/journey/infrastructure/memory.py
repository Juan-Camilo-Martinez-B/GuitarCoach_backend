"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from collections.abc import Iterable
from datetime import date, datetime
from uuid import UUID


class InMemoryJourney:
    def __init__(self) -> None:
        self._milestones: dict[UUID, set[str]] = {}
        self._days: dict[UUID, set[date]] = {}

    async def milestones(self, user_id: UUID) -> set[str]:
        return set(self._milestones.get(user_id, set()))

    async def days(self, user_id: UUID) -> set[date]:
        return set(self._days.get(user_id, set()))

    async def add_milestones(
        self, user_id: UUID, milestones: Iterable[str], when: datetime
    ) -> None:
        self._milestones.setdefault(user_id, set()).update(milestones)

    async def add_days(self, user_id: UUID, days: Iterable[date]) -> None:
        self._days.setdefault(user_id, set()).update(days)
