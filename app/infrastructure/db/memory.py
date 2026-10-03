"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from datetime import date
from uuid import UUID

from app.domain.entities.attempt import Attempt, ChordMetric
from app.domain.entities.report import Report
from app.domain.entities.scrape_job import ScrapeJob
from app.domain.entities.song import Song
from app.domain.entities.user import User


class InMemoryUsers:
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.lower()
        return next((user for user in self._by_id.values() if user.email == normalized), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)


class InMemorySongs:
    def __init__(self) -> None:
        self._items: dict[int, Song] = {}
        self._next_id = 1

    async def add(self, song: Song) -> Song:
        stored = Song(
            title=song.title,
            artist=song.artist,
            song_key=song.song_key,
            bpm=song.bpm,
            chords=song.chords,
            source_url=song.source_url,
            source_name=song.source_name,
            content_hash=song.content_hash,
            id=self._next_id,
        )
        self._items[self._next_id] = stored
        self._next_id += 1
        return stored

    async def get(self, song_id: int) -> Song | None:
        return self._items.get(song_id)

    async def search(self, query: str) -> tuple[Song, ...]:
        needle = query.casefold()
        return tuple(
            song
            for song in self._items.values()
            if needle in song.title.casefold() or needle in song.artist.casefold()
        )

    async def find_by_source_url(self, source_url: str) -> Song | None:
        return next((song for song in self._items.values() if song.source_url == source_url), None)


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


class InMemoryReports:
    def __init__(self) -> None:
        self._items: list[Report] = []

    async def add(self, report: Report) -> None:
        self._items.append(report)

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None:
        return next((item for item in self._items if item.attempt_id == attempt_id), None)

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None:
        return next((item for item in self._items if item.metrics_hash == metrics_hash), None)

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int:
        return 0


class InMemoryJobs:
    def __init__(self) -> None:
        self._items: dict[UUID, ScrapeJob] = {}

    async def add(self, job: ScrapeJob) -> None:
        self._items[job.id] = job

    async def get(self, job_id: UUID) -> ScrapeJob | None:
        return self._items.get(job_id)

    async def save(self, job: ScrapeJob) -> None:
        self._items[job.id] = job


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self.users = InMemoryUsers()
        self.songs = InMemorySongs()
        self.attempts = InMemoryAttempts()
        self.reports = InMemoryReports()
        self.jobs = InMemoryJobs()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None
