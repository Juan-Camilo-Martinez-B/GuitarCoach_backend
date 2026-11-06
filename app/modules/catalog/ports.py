"""Puertos del catálogo. La infraestructura los implementa."""

from typing import Protocol
from uuid import UUID

from app.modules.catalog.domain.scrape_job import ScrapeJob
from app.modules.catalog.domain.song import Song
from app.modules.catalog.domain.study import StudyPlan
from app.shared.persistence.transaction import Transactional


class SongRepository(Protocol):
    async def add(self, song: Song) -> Song: ...

    async def get(self, song_id: int) -> Song | None: ...

    async def search(self, query: str) -> tuple[Song, ...]: ...

    async def find_by_source_url(self, source_url: str) -> Song | None: ...

    async def find_by_content_hash(self, content_hash: str) -> Song | None: ...

    async def update_chart(self, song_id: int, song: Song) -> Song | None: ...


class ScrapeJobRepository(Protocol):
    async def add(self, job: ScrapeJob) -> None: ...

    async def get(self, job_id: UUID) -> ScrapeJob | None: ...

    async def save(self, job: ScrapeJob) -> None: ...


class StudyRepository(Protocol):
    async def get(self, song_id: int) -> StudyPlan | None: ...

    async def save(self, song_id: int, plan: StudyPlan) -> None: ...


class CatalogStore(Transactional, Protocol):
    songs: SongRepository
    jobs: ScrapeJobRepository
    studies: StudyRepository
