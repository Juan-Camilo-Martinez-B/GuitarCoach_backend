"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.attempt import Attempt, ChordMetric
from app.domain.entities.report import Report, ReportContent
from app.domain.entities.scrape_job import ScrapeJob
from app.domain.entities.song import ChartChord, Song
from app.domain.entities.user import User
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord
from app.domain.value_objects.hit_result import HitResult
from app.infrastructure.db.models import (
    AttemptModel,
    ChordMetricModel,
    ReportModel,
    ScrapeJobModel,
    SongModel,
    UserModel,
)


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


def _events_from_summary(raw: dict[str, object]) -> tuple[HitResult, ...]:
    payload = raw.get("events", [])
    if not isinstance(payload, list):
        return ()
    events: list[HitResult] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        detected_raw = item.get("detected")
        detected = Chord.parse(str(detected_raw)) if isinstance(detected_raw, str) else None
        judged = HitResult.judge(
            Chord.parse(str(item["expected"])),
            detected,
            int(item["delta_ms"]),
        )
        events.append(
            HitResult(
                expected=judged.expected,
                detected=judged.detected,
                delta_ms=judged.delta_ms,
                kind=judged.kind,
                bar=int(item.get("bar", 1)),
                confidence=float(item.get("confidence", 1)),
            )
        )
    return tuple(events)


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                display_name=user.display_name,
                level=user.level,
                oauth_subject=user.oauth_subject,
                latency_offset_ms=user.latency_offset_ms,
                created_at=user.created_at,
            )
        )

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email.lower()))
        return None if row is None else _user_to_entity(row)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return None if row is None else _user_to_entity(row)


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
                or_(SongModel.title.ilike(needle), SongModel.artist.ilike(needle))
            )
        )
        return tuple(_song_to_entity(row) for row in rows)

    async def find_by_source_url(self, source_url: str) -> Song | None:
        row = await self._session.scalar(
            select(SongModel).where(SongModel.source_url == source_url)
        )
        return None if row is None else _song_to_entity(row)


class SqlAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, attempt: Attempt, metrics: tuple[ChordMetric, ...]) -> None:
        self._session.add(
            AttemptModel(
                id=attempt.id,
                user_id=attempt.user_id,
                song_id=attempt.song_id,
                bpm=attempt.bpm.value,
                accuracy=attempt.accuracy,
                avg_delta_ms=attempt.avg_delta_ms,
                latency_offset_ms=attempt.latency_offset_ms,
                tuning_cents_avg=attempt.tuning_cents_avg,
                raw_summary={
                    "events": [
                        {
                            "bar": event.bar,
                            "expected": event.expected.symbol,
                            "detected": None if event.detected is None else event.detected.symbol,
                            "delta_ms": event.delta_ms,
                            "confidence": event.confidence,
                            "kind": event.kind.value,
                        }
                        for event in attempt.events
                    ]
                },
                created_at=attempt.created_at,
            )
        )
        for metric in metrics:
            self._session.add(
                ChordMetricModel(
                    attempt_id=attempt.id,
                    chord=metric.chord,
                    accuracy=metric.accuracy,
                    avg_delta_ms=metric.avg_delta_ms,
                    errors=metric.errors,
                )
            )

    async def get(self, attempt_id: UUID) -> Attempt | None:
        row = await self._session.get(AttemptModel, attempt_id)
        return None if row is None else _attempt_to_entity(row)

    async def list_for_user(self, user_id: UUID) -> tuple[Attempt, ...]:
        rows = await self._session.scalars(
            select(AttemptModel).where(AttemptModel.user_id == user_id)
        )
        return tuple(_attempt_to_entity(row) for row in rows)

    async def metrics_for(self, attempt_id: UUID) -> tuple[ChordMetric, ...]:
        rows = await self._session.scalars(
            select(ChordMetricModel).where(ChordMetricModel.attempt_id == attempt_id)
        )
        return tuple(
            ChordMetric(
                chord=row.chord,
                accuracy=float(row.accuracy),
                avg_delta_ms=float(row.avg_delta_ms),
                errors=row.errors,
                id=row.id,
            )
            for row in rows
        )


class SqlReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: Report) -> None:
        self._session.add(
            ReportModel(
                id=report.id,
                attempt_id=report.attempt_id,
                content={
                    "diagnostico": report.content.diagnostico,
                    "ejercicios": list(report.content.ejercicios),
                    "plan_semanal": list(report.content.plan_semanal),
                    "consejos_tecnica": list(report.content.consejos_tecnica),
                },
                model=report.model,
                metrics_hash=report.metrics_hash,
                created_at=report.created_at,
            )
        )

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None:
        row = await self._session.scalar(
            select(ReportModel).where(ReportModel.attempt_id == attempt_id)
        )
        return None if row is None else _report_to_entity(row)

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None:
        row = await self._session.scalar(
            select(ReportModel).where(ReportModel.metrics_hash == metrics_hash)
        )
        return None if row is None else _report_to_entity(row)

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int:
        rows = await self._session.scalars(
            select(ReportModel)
            .join(AttemptModel, AttemptModel.id == ReportModel.attempt_id)
            .where(AttemptModel.user_id == user_id)
        )
        return sum(1 for row in rows if row.created_at.date() == day)


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


class SqlUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = SqlUserRepository(session)
        self.songs = SqlSongRepository(session)
        self.attempts = SqlAttemptRepository(session)
        self.reports = SqlReportRepository(session)
        self.jobs = SqlJobRepository(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def _user_to_entity(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        level=row.level,
        password_hash=row.password_hash,
        oauth_subject=row.oauth_subject,
        latency_offset_ms=row.latency_offset_ms,
        created_at=row.created_at,
    )


def _attempt_to_entity(row: AttemptModel) -> Attempt:
    return Attempt(
        id=row.id,
        user_id=row.user_id,
        song_id=row.song_id,
        bpm=Bpm(row.bpm),
        accuracy=float(row.accuracy),
        avg_delta_ms=float(row.avg_delta_ms),
        latency_offset_ms=row.latency_offset_ms,
        tuning_cents_avg=None if row.tuning_cents_avg is None else float(row.tuning_cents_avg),
        events=_events_from_summary(row.raw_summary),
        created_at=row.created_at,
    )


def _text_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _report_to_entity(row: ReportModel) -> Report:
    content = row.content
    return Report(
        id=row.id,
        attempt_id=row.attempt_id,
        content=ReportContent(
            diagnostico=str(content["diagnostico"]),
            ejercicios=_text_list(content["ejercicios"]),
            plan_semanal=_text_list(content["plan_semanal"]),
            consejos_tecnica=_text_list(content["consejos_tecnica"]),
        ),
        model=row.model,
        metrics_hash=row.metrics_hash,
        created_at=row.created_at,
    )


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
