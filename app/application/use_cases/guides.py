"""Guías privadas: crear sin duplicar, leer y corregir solo las propias."""

from dataclasses import replace
from uuid import UUID, uuid4

from app.application.security import Clock
from app.domain.entities.guide import STATUSES, GuideRecord, SongGuide
from app.domain.entities.song import Song
from app.domain.errors import ConflictError, InvalidValueError, NotFoundError
from app.domain.interfaces.repositories import UnitOfWork
from app.domain.services.chart_import import build_plan, imported_from_guide

PRACTICE_SOURCE = "guia"


class GuideService:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def create(
        self, owner_id: UUID, guide: SongGuide, source_kind: str
    ) -> tuple[GuideRecord, bool]:
        """Devuelve la guía y si es nueva. El mismo contenido no se guarda dos veces."""
        content_hash = guide.digest()
        existing = await self._uow.guides.find_by_hash(owner_id, content_hash)
        if existing is not None:
            return existing, False
        now = self._clock.now()
        record = GuideRecord(
            id=uuid4(),
            owner_id=owner_id,
            song_id=await self._practice_song(guide),
            source_kind=source_kind,
            status="borrador",
            guide=guide,
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
        )
        await self._uow.guides.add(record)
        await self._uow.commit()
        return record, True

    async def list(self, owner_id: UUID) -> tuple[GuideRecord, ...]:
        return await self._uow.guides.list_for_owner(owner_id)

    async def get(self, owner_id: UUID, guide_id: UUID) -> GuideRecord:
        record = await self._uow.guides.get(guide_id)
        # La guía ajena responde igual que la que no existe: no se revela que existe.
        if record is None or record.owner_id != owner_id:
            raise NotFoundError("La guía no existe.")
        return record

    async def update(
        self, owner_id: UUID, guide_id: UUID, guide: SongGuide, status: str
    ) -> GuideRecord:
        if status not in STATUSES:
            raise InvalidValueError("Estado de guía desconocido.")
        current = await self.get(owner_id, guide_id)
        content_hash = guide.digest()
        duplicate = await self._uow.guides.find_by_hash(owner_id, content_hash)
        if duplicate is not None and duplicate.id != guide_id:
            raise ConflictError("Ya tienes otra guía con este mismo contenido.")
        song_id = current.song_id
        if content_hash != current.content_hash or song_id is None:
            song_id = await self._practice_song(guide)
        updated = replace(
            current,
            guide=guide,
            status=status,
            content_hash=content_hash,
            song_id=song_id,
            updated_at=self._clock.now(),
        )
        await self._uow.guides.save(updated)
        await self._uow.commit()
        return updated

    async def _practice_song(self, guide: SongGuide) -> int:
        """La canción que representa la guía en la práctica, compartida si el contenido coincide."""
        content_hash = f"{PRACTICE_SOURCE}:{guide.digest()}"
        song = await self._uow.songs.find_by_content_hash(content_hash)
        if song is None:
            song = await self._uow.songs.add(
                Song(
                    title=guide.title,
                    artist=guide.artist,
                    song_key=guide.song_key,
                    bpm=guide.bpm,
                    chords=guide.chart(),
                    source_url=None,
                    source_name=PRACTICE_SOURCE,
                    content_hash=content_hash,
                )
            )
        if song.id is None:
            raise RuntimeError("La canción de práctica no recibió id.")
        chart = imported_from_guide(guide)
        plan = build_plan(chart.title, chart.song_key, chart.bpm, chart.chords, chart.melody)
        await self._uow.studies.save(song.id, plan)
        return song.id
