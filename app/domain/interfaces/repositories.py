"""Puertos de persistencia. La infraestructura los implementa; el dominio no importa SQLAlchemy."""

from datetime import date
from typing import Protocol
from uuid import UUID

from app.domain.entities.attempt import Attempt, ChordMetric
from app.domain.entities.report import Report
from app.domain.entities.scrape_job import ScrapeJob
from app.domain.entities.song import Song
from app.domain.entities.user import User


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...


class SongRepository(Protocol):
    async def add(self, song: Song) -> Song: ...

    async def get(self, song_id: int) -> Song | None: ...

    async def search(self, query: str) -> tuple[Song, ...]: ...

    async def find_by_source_url(self, source_url: str) -> Song | None: ...


class AttemptRepository(Protocol):
    async def add(self, attempt: Attempt, metrics: tuple[ChordMetric, ...]) -> None: ...

    async def get(self, attempt_id: UUID) -> Attempt | None: ...

    async def list_for_user(self, user_id: UUID) -> tuple[Attempt, ...]: ...

    async def metrics_for(self, attempt_id: UUID) -> tuple[ChordMetric, ...]: ...


class ReportRepository(Protocol):
    async def add(self, report: Report) -> None: ...

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None: ...

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None: ...

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int: ...


class ScrapeJobRepository(Protocol):
    async def add(self, job: ScrapeJob) -> None: ...

    async def get(self, job_id: UUID) -> ScrapeJob | None: ...

    async def save(self, job: ScrapeJob) -> None: ...


class UnitOfWork(Protocol):
    users: UserRepository
    songs: SongRepository
    attempts: AttemptRepository
    reports: ReportRepository
    jobs: ScrapeJobRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
