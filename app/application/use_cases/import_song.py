"""Importa una canción o reutiliza la que ya está en caché por su URL."""

import hashlib
import json
from uuid import UUID, uuid4

from app.application.security import Clock
from app.domain.entities.scrape_job import ScrapeJob
from app.domain.entities.song import Song
from app.domain.errors import NotFoundError
from app.domain.interfaces.repositories import UnitOfWork
from app.domain.value_objects.bpm import Bpm
from app.infrastructure.scraping.base import ParsedChart
from app.infrastructure.scraping.rate_limiter import DomainRateLimiter
from app.infrastructure.scraping.registry import ScraperRegistry
from app.infrastructure.scraping.robots import domain_of, is_allowed


class ImportSong:
    def __init__(
        self,
        uow: UnitOfWork,
        registry: ScraperRegistry,
        limiter: DomainRateLimiter,
        clock: Clock,
        scraper_name: str,
        robots_txt: str,
    ) -> None:
        self._uow = uow
        self._registry = registry
        self._limiter = limiter
        self._clock = clock
        self._scraper_name = scraper_name
        self._robots_txt = robots_txt

    async def start(self, user_id: UUID | None, query: str) -> ScrapeJob:
        now = self._clock.now()
        job = ScrapeJob(
            id=uuid4(),
            user_id=user_id,
            song_id=None,
            status="pending",
            query=query.strip(),
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self._uow.jobs.add(job)
        await self._uow.commit()
        return job

    async def run(self, job_id: UUID) -> None:
        job = await self._uow.jobs.get(job_id)
        if job is None:
            raise NotFoundError("El trabajo no existe.")
        now = self._clock.now()
        running = job.mark_running(now)
        await self._uow.jobs.save(running)
        await self._uow.commit()
        try:
            scraper = self._registry.get(self._scraper_name)
            location = scraper.search(job.query)
            if not is_allowed(self._robots_txt, location):
                raise PermissionError("robots.txt no permite descargar esa URL.")
            await self._limiter.wait(domain_of(location))
            parsed = scraper.collect(job.query)
            song_id = await self._store(parsed)
            await self._uow.jobs.save(running.mark_done(song_id, self._clock.now()))
            await self._uow.commit()
        except Exception as error:
            await self._uow.rollback()
            await self._uow.jobs.save(running.mark_failed(str(error), self._clock.now()))
            await self._uow.commit()
            raise

    async def _store(self, parsed: ParsedChart) -> int:
        cached = await self._uow.songs.find_by_source_url(parsed.source_url)
        if cached is not None and cached.id is not None:
            return cached.id
        stored = await self._uow.songs.add(
            Song(
                title=parsed.title,
                artist=parsed.artist,
                song_key=parsed.song_key,
                bpm=Bpm(parsed.bpm),
                chords=parsed.chords,
                source_url=parsed.source_url,
                source_name=parsed.source_name,
                content_hash=_content_hash(parsed),
            )
        )
        if stored.id is None:
            raise RuntimeError("La canción no recibió id.")
        return stored.id


def _content_hash(parsed: ParsedChart) -> str:
    payload = {
        "artist": parsed.artist,
        "chords": [
            {"bar": chord.bar, "beat": chord.beat, "chord": chord.chord.symbol}
            for chord in parsed.chords
        ],
        "title": parsed.title,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()
