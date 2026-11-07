"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guides.domain.guide import GuideRecord, SongGuide
from app.modules.guides.domain.guide_tab import GuideTab
from app.modules.guides.infrastructure.models import GuideTabModel, SongGuideModel


class SqlGuideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: GuideRecord) -> None:
        self._session.add(
            SongGuideModel(
                id=record.id,
                owner_id=record.owner_id,
                song_id=record.song_id,
                title=record.guide.title,
                artist=record.guide.artist,
                source_kind=record.source_kind,
                status=record.status,
                guide=record.guide.as_dict(),
                content_hash=record.content_hash,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )
        await self._session.flush()

    async def get(self, guide_id: UUID) -> GuideRecord | None:
        row = await self._session.get(SongGuideModel, guide_id)
        return None if row is None else _guide_to_entity(row)

    async def list_for_owner(self, owner_id: UUID) -> tuple[GuideRecord, ...]:
        rows = await self._session.scalars(
            select(SongGuideModel)
            .where(SongGuideModel.owner_id == owner_id)
            .order_by(SongGuideModel.updated_at.desc())
        )
        return tuple(_guide_to_entity(row) for row in rows)

    async def find_by_hash(self, owner_id: UUID, content_hash: str) -> GuideRecord | None:
        row = await self._session.scalar(
            select(SongGuideModel).where(
                SongGuideModel.owner_id == owner_id,
                SongGuideModel.content_hash == content_hash,
            )
        )
        return None if row is None else _guide_to_entity(row)

    async def save(self, record: GuideRecord) -> None:
        row = await self._session.get(SongGuideModel, record.id)
        if row is None:
            await self.add(record)
            return
        row.song_id = record.song_id
        row.title = record.guide.title
        row.artist = record.guide.artist
        row.source_kind = record.source_kind
        row.status = record.status
        row.guide = record.guide.as_dict()
        row.content_hash = record.content_hash
        row.updated_at = record.updated_at
        await self._session.flush()

    async def add_tab(self, tab: GuideTab) -> None:
        self._session.add(GuideTabModel(guide_id=tab.guide_id, format=tab.format, data=tab.data))
        await self._session.flush()

    async def get_tab(self, guide_id: UUID) -> GuideTab | None:
        row = await self._session.get(GuideTabModel, guide_id)
        return None if row is None else GuideTab(row.guide_id, row.format, row.data)

    async def delete(self, guide_id: UUID) -> None:
        tab = await self._session.get(GuideTabModel, guide_id)
        if tab is not None:
            await self._session.delete(tab)
        row = await self._session.get(SongGuideModel, guide_id)
        if row is not None:
            await self._session.delete(row)
        await self._session.flush()


def _guide_to_entity(row: SongGuideModel) -> GuideRecord:
    return GuideRecord(
        id=row.id,
        owner_id=row.owner_id,
        song_id=row.song_id,
        source_kind=row.source_kind,
        status=row.status,
        guide=SongGuide.from_dict(row.guide),
        content_hash=row.content_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
