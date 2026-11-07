"""Puertos de las guías. La infraestructura los implementa."""

from typing import Protocol
from uuid import UUID

from app.modules.catalog.public import SongRepository, StudyRepository
from app.modules.guides.domain.guide import GuideRecord
from app.modules.guides.domain.guide_tab import GuideTab
from app.shared.persistence.transaction import Transactional


class GuideRepository(Protocol):
    async def add(self, record: GuideRecord) -> None: ...

    async def get(self, guide_id: UUID) -> GuideRecord | None: ...

    async def list_for_owner(self, owner_id: UUID) -> tuple[GuideRecord, ...]: ...

    async def find_by_hash(self, owner_id: UUID, content_hash: str) -> GuideRecord | None: ...

    async def save(self, record: GuideRecord) -> None: ...

    async def add_tab(self, tab: GuideTab) -> None: ...

    async def get_tab(self, guide_id: UUID) -> GuideTab | None: ...

    async def delete(self, guide_id: UUID) -> None: ...


class GuidesStore(Transactional, Protocol):
    guides: GuideRepository
    songs: SongRepository
    studies: StudyRepository
