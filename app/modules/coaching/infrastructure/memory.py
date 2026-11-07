"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from datetime import date
from uuid import UUID

from app.modules.coaching.domain.report import Report
from app.modules.practice.public import AttemptRepository


class InMemoryReports:
    def __init__(self, attempts: AttemptRepository) -> None:
        self._items: list[Report] = []
        self._attempts = attempts

    async def add(self, report: Report) -> None:
        self._items.append(report)

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None:
        return next((item for item in self._items if item.attempt_id == attempt_id), None)

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None:
        return next((item for item in self._items if item.metrics_hash == metrics_hash), None)

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int:
        total = 0
        for report in self._items:
            attempt = await self._attempts.get(report.attempt_id)
            if attempt is None or attempt.user_id != user_id:
                continue
            if report.created_at.date() == day:
                total += 1
        return total

    async def delete_for_attempt(self, attempt_id: UUID) -> None:
        self._items = [item for item in self._items if item.attempt_id != attempt_id]
