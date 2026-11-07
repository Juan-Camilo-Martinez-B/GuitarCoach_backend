"""Búsqueda local e importación asíncrona de canciones."""

import os
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.modules.catalog.application.scraping.registry import ScraperRegistry
from app.modules.catalog.infrastructure.scraping.factory import build_importer
from app.modules.catalog.ports import CatalogStore
from app.shared.config import Settings
from app.shared.errors import NotFoundError
from app.shared.http.deps import current_uow
from app.shared.tasks.local_dispatcher import LocalTaskDispatcher

router = APIRouter(tags=["songs"])


class ImportBody(BaseModel):
    query: str = Field(min_length=1)


class JobResponse(BaseModel):
    id: str
    status: str
    song_id: int | None = None
    error: str | None = None


def _store(request: Request) -> CatalogStore:
    return cast(CatalogStore, current_uow(request))


def _dispatcher(request: Request) -> LocalTaskDispatcher:
    dispatcher = request.app.state.dispatcher
    if not isinstance(dispatcher, LocalTaskDispatcher):
        raise RuntimeError("El despachador no está configurado.")
    return dispatcher


@router.get("/songs")
async def search_songs(request: Request, q: str = Query(min_length=1)) -> list[dict[str, object]]:
    songs = await _store(request).songs.search(q)
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
    job = await build_importer(_store(request), settings, registry).start(None, body.query)
    dispatcher = _dispatcher(request)
    dispatch_id = dispatcher.enqueue("import_song", {"job_id": str(job.id)})
    # En Vercel el proceso se congela al responder. La importación tiene que terminar aquí.
    if os.environ.get("VERCEL"):
        await dispatcher.join(dispatch_id)
        stored = await _store(request).jobs.get(job.id)
        if stored is not None:
            job = stored
    return JobResponse(id=str(job.id), status=job.status, song_id=job.song_id, error=job.error)


@router.get("/songs/{song_id}/study")
async def read_study(song_id: int, request: Request) -> dict[str, object]:
    plan = await _store(request).studies.get(song_id)
    if plan is None:
        raise NotFoundError("Esta canción todavía no tiene análisis.")
    return plan.as_dict()


@router.get("/jobs/{job_id}")
async def job_status(job_id: UUID, request: Request) -> JobResponse:
    job = await _store(request).jobs.get(job_id)
    if job is None:
        raise NotFoundError("El trabajo no existe.")
    return JobResponse(id=str(job.id), status=job.status, song_id=job.song_id, error=job.error)
