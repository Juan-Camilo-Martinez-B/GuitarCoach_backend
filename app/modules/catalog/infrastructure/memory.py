"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from uuid import UUID

from app.modules.catalog.domain.scrape_job import ScrapeJob
from app.modules.catalog.domain.song import PRIVATE_SOURCES, Song
from app.modules.catalog.domain.study import StudyPlan


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
            if song.source_name not in PRIVATE_SOURCES
            and (needle in song.title.casefold() or needle in song.artist.casefold())
        )

    async def find_by_source_url(self, source_url: str) -> Song | None:
        return next((song for song in self._items.values() if song.source_url == source_url), None)

    async def find_by_content_hash(self, content_hash: str) -> Song | None:
        return next(
            (song for song in self._items.values() if song.content_hash == content_hash),
            None,
        )

    async def update_chart(self, song_id: int, song: Song) -> Song | None:
        current = self._items.get(song_id)
        if current is None:
            return None
        stored = Song(
            title=song.title,
            artist=song.artist,
            song_key=song.song_key,
            bpm=song.bpm,
            chords=song.chords,
            source_url=song.source_url,
            source_name=song.source_name,
            content_hash=song.content_hash,
            id=song_id,
        )
        self._items[song_id] = stored
        return stored


class InMemoryJobs:
    def __init__(self) -> None:
        self._items: dict[UUID, ScrapeJob] = {}

    async def add(self, job: ScrapeJob) -> None:
        self._items[job.id] = job

    async def get(self, job_id: UUID) -> ScrapeJob | None:
        return self._items.get(job_id)

    async def save(self, job: ScrapeJob) -> None:
        self._items[job.id] = job


class InMemoryStudies:
    def __init__(self) -> None:
        self._items: dict[int, StudyPlan] = {}

    async def get(self, song_id: int) -> StudyPlan | None:
        return self._items.get(song_id)

    async def save(self, song_id: int, plan: StudyPlan) -> None:
        self._items[song_id] = plan
