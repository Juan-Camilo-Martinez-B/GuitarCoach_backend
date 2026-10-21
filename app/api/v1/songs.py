"""Búsqueda local e importación asíncrona de canciones."""

from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import current_uow
from app.api.v1.attempts import _bearer_user_id
from app.core.config import Settings
from app.domain.entities.song import ChartChord, Song
from app.domain.errors import NotFoundError
from app.domain.services.chart_import import build_plan, parse_chart
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord
from app.infrastructure.queue.local_dispatcher import LocalTaskDispatcher
from app.infrastructure.scraping.factory import build_importer
from app.infrastructure.scraping.registry import ScraperRegistry

router = APIRouter(tags=["songs"])


class ImportBody(BaseModel):
    query: str = Field(min_length=1)


class JobResponse(BaseModel):
    id: str
    status: str
    song_id: int | None = None
    error: str | None = None


def _dispatcher(request: Request) -> LocalTaskDispatcher:
    dispatcher = request.app.state.dispatcher
    if not isinstance(dispatcher, LocalTaskDispatcher):
        raise RuntimeError("El despachador no está configurado.")
    return dispatcher


@router.get("/songs")
async def search_songs(request: Request, q: str = Query(min_length=1)) -> list[dict[str, object]]:
    songs = await current_uow(request).songs.search(q)
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
    settings = request.app.state.settings
    registry = request.app.state.registry
    if not isinstance(settings, Settings) or not isinstance(registry, ScraperRegistry):
        raise RuntimeError("La importación no está configurada.")
    job = await build_importer(current_uow(request), settings, registry).start(None, body.query)
    _dispatcher(request).enqueue("import_song", {"job_id": str(job.id)})
    return JobResponse(id=str(job.id), status=job.status)


@router.get("/songs/{song_id}/study")
async def read_study(song_id: int, request: Request) -> dict[str, object]:
    plan = await current_uow(request).studies.get(song_id)
    if plan is None:
        raise NotFoundError("Esta canción todavía no tiene análisis.")
    return plan.as_dict()


@router.post("/songs/upload", status_code=201)
async def upload_song(
    request: Request,
    file: UploadFile,
    authorization: str = Header(),
) -> dict[str, object]:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    _bearer_user_id(authorization, settings)
    chart = parse_chart(file.filename or "carta.cho", await file.read())
    uow = current_uow(request)
    song = await uow.songs.find_by_content_hash(chart.digest())
    if song is None:
        song = await uow.songs.add(
            Song(
                title=chart.title,
                artist=chart.artist,
                song_key=chart.song_key,
                bpm=Bpm(chart.bpm),
                chords=tuple(
                    ChartChord(bar, beat, Chord.parse(symbol)) for bar, beat, symbol in chart.chords
                ),
                source_url=f"upload:{chart.digest()}",
                source_name="archivo",
                content_hash=chart.digest(),
            )
        )
    if song.id is None:
        raise RuntimeError("La canción no recibió id.")
    plan = build_plan(song.title, song.song_key, song.bpm.value, chart.chords, chart.melody)
    await uow.studies.save(song.id, plan)
    await uow.commit()
    return {
        "song": {
            "id": song.id,
            "title": song.title,
            "artist": song.artist,
            "song_key": song.song_key,
            "bpm": song.bpm.value,
            "chords": [
                {"bar": chord.bar, "beat": chord.beat, "chord": chord.chord.symbol}
                for chord in song.chords
            ],
        },
        "study": plan.as_dict(),
    }


@router.get("/jobs/{job_id}")
async def job_status(job_id: UUID, request: Request) -> JobResponse:
    job = await current_uow(request).jobs.get(job_id)
    if job is None:
        raise NotFoundError("El trabajo no existe.")
    return JobResponse(id=str(job.id), status=job.status, song_id=job.song_id, error=job.error)
