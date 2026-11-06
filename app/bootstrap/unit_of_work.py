"""Une los repositorios de todos los módulos en una sola transacción por petición."""

from typing import Protocol

from app.modules.catalog.infrastructure.memory import InMemoryJobs, InMemorySongs, InMemoryStudies
from app.modules.catalog.infrastructure.sql import (
    SqlJobRepository,
    SqlSongRepository,
    SqlStudyRepository,
)
from app.modules.catalog.ports import CatalogStore
from app.modules.coaching.infrastructure.memory import InMemoryReports
from app.modules.coaching.infrastructure.sql import SqlReportRepository
from app.modules.coaching.ports import CoachingStore
from app.modules.guides.infrastructure.memory import InMemoryGuides
from app.modules.guides.infrastructure.sql import SqlGuideRepository
from app.modules.guides.ports import GuidesStore
from app.modules.identity.infrastructure.memory import InMemoryUsers
from app.modules.identity.infrastructure.sql import SqlUserRepository
from app.modules.identity.ports import IdentityStore
from app.modules.journey.infrastructure.memory import InMemoryJourney
from app.modules.journey.infrastructure.sql import SqlJourneyRepository
from app.modules.journey.ports import JourneyStore
from app.modules.learning.infrastructure.memory import InMemoryLessons
from app.modules.learning.infrastructure.sql import SqlLessonRepository
from app.modules.learning.ports import LearningStore
from app.modules.practice.infrastructure.memory import InMemoryAttempts
from app.modules.practice.infrastructure.sql import SqlAttemptRepository
from app.modules.practice.ports import PracticeStore
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork(
    IdentityStore,
    CatalogStore,
    GuidesStore,
    PracticeStore,
    CoachingStore,
    LearningStore,
    JourneyStore,
    Protocol,
):
    """El almacén completo. Solo la composición lo conoce; cada módulo ve su parte."""


class SqlUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = SqlUserRepository(session)
        self.songs = SqlSongRepository(session)
        self.attempts = SqlAttemptRepository(session)
        self.reports = SqlReportRepository(session)
        self.jobs = SqlJobRepository(session)
        self.lessons = SqlLessonRepository(session)
        self.studies = SqlStudyRepository(session)
        self.guides = SqlGuideRepository(session)
        self.journey = SqlJourneyRepository(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.users = InMemoryUsers()
        self.songs = InMemorySongs()
        self.attempts = InMemoryAttempts()
        self.reports = InMemoryReports(self.attempts)
        self.jobs = InMemoryJobs()
        self.lessons = InMemoryLessons()
        self.studies = InMemoryStudies()
        self.guides = InMemoryGuides()
        self.journey = InMemoryJourney()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None
