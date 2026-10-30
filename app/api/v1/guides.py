"""Guías de estudio de canciones elegidas por el usuario. Cada guía es privada de su dueño."""

import asyncio
import time
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Form, Header, Request, Response, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import current_uow
from app.api.middleware.rate_limit import SlidingWindowLimiter
from app.api.v1.attempts import _bearer_user_id
from app.application.security import SystemClock
from app.application.use_cases.guides import GuideService
from app.core.config import Settings
from app.domain.entities.guide import GuideRecord, SongGuide
from app.domain.errors import ExternalServiceError, RateLimitExceededError
from app.domain.services.guide_import import (
    MAX_BYTES,
    guide_from_file,
    guide_from_text,
    guide_from_timeline,
    parse_time_signature,
)
from app.infrastructure.audio.analysis import MAX_BYTES as MAX_AUDIO_BYTES
from app.infrastructure.audio.analysis import analyze_bytes

router = APIRouter(tags=["guides"])

MAX_PASTED_CHARS = 20_000


class PasteBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    artist: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=MAX_PASTED_CHARS)
    bpm: int | None = Field(default=None, ge=20, le=300)
    time: str | None = Field(default=None, max_length=5)
    capo: int | None = Field(default=None, ge=0, le=12)
    strum: str | None = Field(default=None, max_length=32)


class StrumDocument(BaseModel):
    directions: list[Literal["abajo", "arriba", "apagado"]] = Field(min_length=1, max_length=32)
    beats: list[float] = Field(min_length=1, max_length=32)


class SectionDocument(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start: float = Field(ge=0)
    beats: float = Field(gt=0)
    strum: StrumDocument


class ChordDocument(BaseModel):
    start: float = Field(ge=0)
    beats: float = Field(gt=0)
    chord: str = Field(min_length=1, max_length=12)


class NoteDocument(BaseModel):
    start: float = Field(ge=0)
    beats: float = Field(gt=0)
    midi: int


class GuideDocument(BaseModel):
    """Sin campo de letra: la guía guarda acordes, secciones, rasgueo y melodía."""

    version: int = 1
    title: str = Field(min_length=1, max_length=120)
    artist: str = Field(min_length=1, max_length=120)
    song_key: str | None = Field(default=None, max_length=12)
    bpm: int = Field(ge=20, le=300)
    beats_per_bar: float = Field(ge=1, le=12)
    capo: int = Field(default=0, ge=0, le=12)
    sections: list[SectionDocument] = Field(min_length=1, max_length=40)
    chords: list[ChordDocument] = Field(min_length=1, max_length=2000)
    melody: list[NoteDocument] = Field(default_factory=list, max_length=4000)


class UpdateBody(BaseModel):
    status: Literal["borrador", "revisada"]
    guide: GuideDocument


class GuideSummary(BaseModel):
    id: str
    song_id: int | None
    title: str
    artist: str
    bpm: int
    source_kind: str
    status: str
    updated_at: datetime


class GuideResponse(GuideSummary):
    guide: dict[str, object]


def _service(request: Request) -> GuideService:
    return GuideService(current_uow(request), SystemClock())


def _owner(request: Request, authorization: str) -> UUID:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    return _bearer_user_id(authorization, settings)


def _summary(record: GuideRecord) -> GuideSummary:
    return GuideSummary(
        id=str(record.id),
        song_id=record.song_id,
        title=record.guide.title,
        artist=record.guide.artist,
        bpm=record.guide.bpm.value,
        source_kind=record.source_kind,
        status=record.status,
        updated_at=record.updated_at,
    )


def _full(record: GuideRecord) -> GuideResponse:
    return GuideResponse(**_summary(record).model_dump(), guide=record.guide.as_dict())


@router.post("/guides/paste", status_code=201)
async def paste_guide(
    body: PasteBody,
    request: Request,
    response: Response,
    authorization: str = Header(),
) -> GuideResponse:
    owner_id = _owner(request, authorization)
    guide = guide_from_text(
        body.text,
        body.title,
        title=body.title,
        artist=body.artist,
        bpm=body.bpm,
        beats_per_bar=parse_time_signature(body.time) if body.time else None,
        capo=body.capo,
        strum=body.strum,
    )
    record, created = await _service(request).create(owner_id, guide, "pegado")
    if not created:
        response.status_code = 200
    return _full(record)


@router.post("/guides/upload", status_code=201)
async def upload_guide(
    file: UploadFile,
    request: Request,
    response: Response,
    authorization: str = Header(),
) -> GuideResponse:
    owner_id = _owner(request, authorization)
    # Se lee un byte de más para detectar el exceso sin cargar archivos enormes.
    raw = await file.read(MAX_BYTES + 1)
    guide, kind = guide_from_file(file.filename or "carta.cho", raw)
    record, created = await _service(request).create(owner_id, guide, kind)
    if not created:
        response.status_code = 200
    return _full(record)


@router.post("/guides/from-audio", status_code=201)
async def guide_from_audio(
    file: UploadFile,
    request: Request,
    response: Response,
    title: str = Form(min_length=1, max_length=120),
    artist: str = Form(min_length=1, max_length=120),
    melody: bool = Form(default=False),
    authorization: str = Header(),
) -> GuideResponse:
    """Analiza un audio propio y deja una guía en borrador. El audio no se guarda."""
    owner_id = _owner(request, authorization)
    limiter = request.app.state.audio_limiter
    slots = request.app.state.audio_slots
    settings = request.app.state.settings
    if not isinstance(limiter, SlidingWindowLimiter) or not isinstance(settings, Settings):
        raise RuntimeError("El análisis de audio no está configurado.")
    if not limiter.allow(str(owner_id), time.monotonic()):
        raise RateLimitExceededError("Llegaste al límite de análisis de audio por hoy.")
    raw = await file.read(MAX_AUDIO_BYTES + 1)
    async with slots:
        try:
            analysis = await asyncio.wait_for(
                asyncio.to_thread(analyze_bytes, raw, melody=melody),
                timeout=settings.audio_timeout_seconds,
            )
        except TimeoutError as error:
            raise ExternalServiceError(
                "El análisis tardó demasiado. Prueba con un audio más corto."
            ) from error
    guide = guide_from_timeline(
        title,
        artist,
        analysis.bpm,
        [(chord.start, chord.beats, chord.symbol) for chord in analysis.chords],
        [(note.start, note.beats, note.midi) for note in analysis.melody],
    )
    record, created = await _service(request).create(owner_id, guide, "audio")
    if not created:
        response.status_code = 200
    return _full(record)


@router.get("/guides")
async def list_guides(request: Request, authorization: str = Header()) -> list[GuideSummary]:
    owner_id = _owner(request, authorization)
    return [_summary(record) for record in await _service(request).list(owner_id)]


@router.get("/guides/{guide_id}")
async def read_guide(
    guide_id: UUID, request: Request, authorization: str = Header()
) -> GuideResponse:
    owner_id = _owner(request, authorization)
    return _full(await _service(request).get(owner_id, guide_id))


@router.put("/guides/{guide_id}")
async def update_guide(
    guide_id: UUID,
    body: UpdateBody,
    request: Request,
    authorization: str = Header(),
) -> GuideResponse:
    owner_id = _owner(request, authorization)
    guide = SongGuide.from_dict(body.guide.model_dump())
    record = await _service(request).update(owner_id, guide_id, guide, body.status)
    return _full(record)
