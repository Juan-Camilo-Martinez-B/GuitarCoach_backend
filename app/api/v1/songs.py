"""Búsqueda local e importación asíncrona de canciones."""

from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.application.use_cases.import_song import ImportSong
from app.domain.errors import NotFoundError
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.queue.local_dispatcher import LocalTaskDispatcher

router = APIRouter(tags=["songs"])


class ImportBody(BaseModel):
    query: str = Field(min_length=1)


class JobResponse(BaseModel):
    id: str
    status: str
    song_id: int | None = None
    error: str | None = None


def _importer(request: Request) -> ImportSong:
    importer = request.app.state.importer
    if not isinstance(importer, ImportSong):
        raise RuntimeError("El importador no está configurado.")
    return importer


def _dispatcher(request: Request) -> LocalTaskDispatcher:
    dispatcher = request.app.state.dispatcher
    if not isinstance(dispatcher, LocalTaskDispatcher):
        raise RuntimeError("El despachador no está configurado.")
    return dispatcher


@router.get("/songs")
async def search_songs(request: Request, q: str = Query(min_length=1)) -> list[dict[str, object]]:
    uow: UnitOfWork = request.app.state.uow
    songs = await uow.songs.search(q)
    return [
        {
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "song_key": song.song_key,
            "bpm": song.bpm.value,
            "chords": [
                {"bar": chord.bar, "beat": chord.beat, "chord": chord.chord.symbol}
                for chord in song.chords
            ],
        }
        for song in songs
    ]


@router.post("/songs/import", status_code=202)
async def import_song(body: ImportBody, request: Request) -> JobResponse:
    importer = _importer(request)
    job = await importer.start(None, body.query)
    _dispatcher(request).enqueue("import_song", {"job_id": str(job.id)})
    return JobResponse(id=str(job.id), status=job.status)


@router.get("/jobs/{job_id}")
async def job_status(job_id: UUID, request: Request) -> JobResponse:
    uow: UnitOfWork = request.app.state.uow
    job = await uow.jobs.get(job_id)
    if job is None:
        raise NotFoundError("El trabajo no existe.")
    return JobResponse(id=str(job.id), status=job.status, song_id=job.song_id, error=job.error)
