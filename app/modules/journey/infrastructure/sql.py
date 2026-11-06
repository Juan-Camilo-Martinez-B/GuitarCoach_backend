"""Repositorio SQLAlchemy del diario. Insertar lo repetido no hace nada."""

from collections.abc import Iterable
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.journey.infrastructure.models import JourneyMilestoneModel, PracticeDayModel


class SqlJourneyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def milestones(self, user_id: UUID) -> set[str]:
        rows = await self._session.scalars(
            select(JourneyMilestoneModel.milestone).where(JourneyMilestoneModel.user_id == user_id)
        )
        return set(rows)

    async def days(self, user_id: UUID) -> set[date]:
        rows = await self._session.scalars(
            select(PracticeDayModel.day).where(PracticeDayModel.user_id == user_id)
        )
        return set(rows)

    async def add_milestones(
        self, user_id: UUID, milestones: Iterable[str], when: datetime
    ) -> None:
        values = [
            {"user_id": user_id, "milestone": milestone, "achieved_at": when}
            for milestone in milestones
        ]
        if values:
            await self._session.execute(
                insert(JourneyMilestoneModel).values(values).on_conflict_do_nothing()
            )

    async def add_days(self, user_id: UUID, days: Iterable[date]) -> None:
        values = [{"user_id": user_id, "day": day} for day in days]
        if values:
            await self._session.execute(
                insert(PracticeDayModel).values(values).on_conflict_do_nothing()
            )
