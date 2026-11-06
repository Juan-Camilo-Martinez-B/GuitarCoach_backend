"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.domain.scrape_job import ScrapeJob
from app.modules.catalog.domain.song import PRIVATE_SOURCES, ChartChord, Song
from app.modules.catalog.domain.study import StudyPlan
from app.modules.catalog.infrastructure.models import ScrapeJobModel, SongModel, SongStudyModel
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("Se esperaba un número entero.")
    return int(value)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError("Se esperaba un número.")
    return float(value)


def _song_to_entity(row: SongModel) -> Song:
    chords = tuple(
        ChartChord(
            bar=_as_int(item["bar"]),
            beat=_as_float(item["beat"]),
            chord=Chord.parse(str(item["chord"])),
        )
        for item in row.chords
    )
    return Song(
        title=row.title,
        artist=row.artist,
        song_key=row.song_key,
        bpm=Bpm(row.bpm),
        chords=chords,
        source_url=row.source_url,
        source_name=row.source_name,
        content_hash=row.content_hash,
        id=row.id,
    )


class SqlSongRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, song: Song) -> Song:
        row = SongModel(
            title=song.title,
            artist=song.artist,
            song_key=song.song_key,
            bpm=song.bpm.value,
            chords=[
                {"bar": chord.bar, "beat": chord.beat, "chord": chord.chord.symbol}
                for chord in song.chords
            ],
            source_url=song.source_url,
            source_name=song.source_name,
            content_hash=song.content_hash,
        )
        self._session.add(row)
        await self._session.flush()
        return _song_to_entity(row)

    async def get(self, song_id: int) -> Song | None:
        row = await self._session.get(SongModel, song_id)
        return None if row is None else _song_to_entity(row)

    async def search(self, query: str) -> tuple[Song, ...]:
        needle = f"%{query.strip()}%"
        rows = await self._session.scalars(
            select(SongModel).where(
                and_(
                    or_(SongModel.title.ilike(needle), SongModel.artist.ilike(needle)),
                    or_(
                        SongModel.source_name.is_(None),
                        SongModel.source_name.not_in(PRIVATE_SOURCES),
                    ),
                )
            )
        )
        return tuple(_song_to_entity(row) for row in rows)

    async def find_by_source_url(self, source_url: str) -> Song | None:
        row = await self._session.scalar(
            select(SongModel).where(SongModel.source_url == source_url)
        )
        return None if row is None else _song_to_entity(row)

    async def find_by_content_hash(self, content_hash: str) -> Song | None:
        row = await self._session.scalar(
            select(SongModel).where(SongModel.content_hash == content_hash)
        )
        return None if row is None else _song_to_entity(row)

    async def update_chart(self, song_id: int, song: Song) -> Song | None:
        row = await self._session.get(SongModel, song_id)
        if row is None:
            return None
        row.song_key = song.song_key
        row.bpm = song.bpm.value
        row.chords = [
            {"bar": chord.bar, "beat": chord.beat, "chord": chord.chord.symbol}
            for chord in song.chords
        ]
        await self._session.flush()
        return _song_to_entity(row)


class SqlJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: ScrapeJob) -> None:
        self._session.add(_job_model(job))

    async def get(self, job_id: UUID) -> ScrapeJob | None:
        row = await self._session.get(ScrapeJobModel, job_id)
        return None if row is None else _job_to_entity(row)

    async def save(self, job: ScrapeJob) -> None:
        row = await self._session.get(ScrapeJobModel, job.id)
        if row is None:
            self._session.add(_job_model(job))
            return
        row.status = job.status
        row.song_id = job.song_id
        row.error = job.error
        row.updated_at = job.updated_at


class SqlStudyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, song_id: int) -> StudyPlan | None:
        row = await self._session.get(SongStudyModel, song_id)
        if row is None:
            return None
        return StudyPlan.from_dict(row.plan)

    async def save(self, song_id: int, plan: StudyPlan) -> None:
        row = await self._session.get(SongStudyModel, song_id)
        if row is None:
            self._session.add(SongStudyModel(song_id=song_id, plan=plan.as_dict()))
            return
        row.plan = plan.as_dict()


def _job_model(job: ScrapeJob) -> ScrapeJobModel:
    return ScrapeJobModel(
        id=job.id,
        user_id=job.user_id,
        song_id=job.song_id,
        status=job.status,
        query=job.query,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_to_entity(row: ScrapeJobModel) -> ScrapeJob:
    return ScrapeJob(
        id=row.id,
        user_id=row.user_id,
        song_id=row.song_id,
        status=row.status,
        query=row.query,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
