"""Guías de estudio de canciones elegidas por el usuario. Cada guía es privada de su dueño.

Una guía nace de una tablatura de Guitar Pro: el navegador la lee y el servidor la valida.
"""

import json
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Form, Header, Request, Response, UploadFile
from pydantic import BaseModel, Field, ValidationError

from app.modules.catalog.public import ChartChord, Song, build_plan
from app.modules.guides.application.service import GuideService
from app.modules.guides.domain.chart_import import parse_chart
from app.modules.guides.domain.guide import GuideRecord, SongGuide
from app.modules.guides.domain.guide_tab import MAX_TAB_BYTES, sniff_tab
from app.modules.guides.ports import GuidesStore
from app.modules.identity.public import bearer_user_id
from app.shared.clock import SystemClock
from app.shared.config import Settings
from app.shared.errors import InvalidValueError
from app.shared.http.deps import current_uow
from app.shared.music.bpm import Bpm
from app.shared.music.chord import Chord

router = APIRouter(tags=["guides"])


def _store(request: Request) -> GuidesStore:
    return cast(GuidesStore, current_uow(request))


# La guía de una tablatura larga trae miles de notas y golpes.
MAX_GUIDE_JSON_CHARS = 2_000_000


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


class TempoDocument(BaseModel):
    pulse: float = Field(ge=0)
    us_per_quarter: int = Field(ge=200_000, le=3_000_000)


class EventDocument(BaseModel):
    pulse: float = Field(ge=0)
    span: float = Field(gt=0, le=64)
    direction: Literal["abajo", "arriba", "apagado"]
    contact: Literal["golpe", "chuck", "aire"]
    velocity: float = Field(ge=0, le=1)
    origin: Literal["escrito", "inferido", "editado", "leccion"]


class GuideDocument(BaseModel):
    """Sin campo de letra: la guía guarda acordes, secciones, rasgueo y la lista de golpes."""

    version: int = 2
    title: str = Field(min_length=1, max_length=120)
    artist: str = Field(min_length=1, max_length=120)
    song_key: str | None = Field(default=None, max_length=12)
    bpm: int = Field(ge=20, le=300)
    beats_per_bar: float = Field(ge=1, le=12)
    capo: int = Field(default=0, ge=0, le=12)
    sections: list[SectionDocument] = Field(min_length=1, max_length=40)
    chords: list[ChordDocument] = Field(min_length=1, max_length=2000)
    melody: list[NoteDocument] = Field(default_factory=list, max_length=4000)
    tempo: list[TempoDocument] = Field(default_factory=list, max_length=64)
    events: list[EventDocument] = Field(default_factory=list, max_length=8000)


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
    return GuideService(_store(request), SystemClock())


def _owner(request: Request, authorization: str) -> UUID:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    return bearer_user_id(authorization, settings)


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


@router.post("/guides/from-tab", status_code=201)
async def guide_from_tab(
    file: UploadFile,
    request: Request,
    response: Response,
    guide: str = Form(min_length=2, max_length=MAX_GUIDE_JSON_CHARS),
    authorization: str = Header(),
) -> GuideResponse:
    """Guarda una tablatura con la guía que el navegador leyó de ella.

    El servidor no confía en el cliente: valida la guía con el mismo esquema que una
    corrección y reconoce el formato del archivo por su contenido.
    """
    owner_id = _owner(request, authorization)
    raw = await file.read(MAX_TAB_BYTES + 1)
    if len(raw) > MAX_TAB_BYTES:
        raise InvalidValueError("La tablatura supera 5 MB.")
    tab_format = sniff_tab(raw)
    if tab_format is None:
        raise InvalidValueError("Sube una tablatura Guitar Pro, MusicXML o MIDI.")
    try:
        document = GuideDocument.model_validate(json.loads(guide))
    except (json.JSONDecodeError, ValidationError) as error:
        raise InvalidValueError("La guía de la tablatura no es válida.") from error
    parsed = SongGuide.from_dict(document.model_dump())
    record, created = await _service(request).create_from_tab(owner_id, parsed, tab_format, raw)
    if not created:
        response.status_code = 200
    return _full(record)


@router.get("/guides/{guide_id}/tab")
async def read_guide_tab(
    guide_id: UUID, request: Request, authorization: str = Header()
) -> Response:
    owner_id = _owner(request, authorization)
    tab = await _service(request).tab(owner_id, guide_id)
    return Response(
        content=tab.data,
        media_type="application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600", "X-Tab-Format": tab.format},
    )


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


@router.delete("/guides/{guide_id}", status_code=204)
async def delete_guide(guide_id: UUID, request: Request, authorization: str = Header()) -> Response:
    """Borra la guía del alumno y el archivo de tablatura que la acompaña."""
    owner_id = _owner(request, authorization)
    await _service(request).delete(owner_id, guide_id)
    return Response(status_code=204)


@router.post("/songs/upload", status_code=201, tags=["songs"])
async def upload_song(
    request: Request,
    file: UploadFile,
    authorization: str = Header(),
) -> dict[str, object]:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    bearer_user_id(authorization, settings)
    chart = parse_chart(file.filename or "carta.cho", await file.read())
    uow = _store(request)
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
