"""Puertos del tutor. La infraestructura los implementa."""

from datetime import date
from typing import Protocol
from uuid import UUID

from app.modules.catalog.public import SongRepository
from app.modules.coaching.domain.report import Report, ReportContent
from app.modules.learning.public import LessonRepository
from app.modules.practice.public import AttemptRepository
from app.shared.persistence.transaction import Transactional


class ReportRepository(Protocol):
    async def add(self, report: Report) -> None: ...

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None: ...

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None: ...

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int: ...


class Tutor(Protocol):
    async def advise(self, prompt: str) -> ReportContent: ...


class CoachingStore(Transactional, Protocol):
    reports: ReportRepository
    attempts: AttemptRepository
    songs: SongRepository
    lessons: LessonRepository
