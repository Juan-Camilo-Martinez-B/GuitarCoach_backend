"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from uuid import UUID

from app.modules.guides.domain.guide import GuideRecord
from app.modules.guides.domain.guide_tab import GuideTab


class InMemoryGuides:
    def __init__(self) -> None:
        self._items: dict[UUID, GuideRecord] = {}
        self._tabs: dict[UUID, GuideTab] = {}

    async def add(self, record: GuideRecord) -> None:
        self._items[record.id] = record

    async def get(self, guide_id: UUID) -> GuideRecord | None:
        return self._items.get(guide_id)

    async def list_for_owner(self, owner_id: UUID) -> tuple[GuideRecord, ...]:
        owned = (item for item in self._items.values() if item.owner_id == owner_id)
        return tuple(sorted(owned, key=lambda item: item.updated_at, reverse=True))

    async def find_by_hash(self, owner_id: UUID, content_hash: str) -> GuideRecord | None:
        return next(
            (
                item
                for item in self._items.values()
                if item.owner_id == owner_id and item.content_hash == content_hash
            ),
            None,
        )

    async def save(self, record: GuideRecord) -> None:
        self._items[record.id] = record

    async def add_tab(self, tab: GuideTab) -> None:
        self._tabs[tab.guide_id] = tab

    async def get_tab(self, guide_id: UUID) -> GuideTab | None:
        return self._tabs.get(guide_id)

    async def delete(self, guide_id: UUID) -> None:
        self._items.pop(guide_id, None)
        self._tabs.pop(guide_id, None)
