"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.infrastructure.models import LessonProgressModel, StudyCheckinModel


class SqlLessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def completed(self, user_id: UUID) -> dict[str, datetime]:
        rows = await self._session.scalars(
            select(LessonProgressModel).where(LessonProgressModel.user_id == user_id)
        )
        return {row.lesson_id: row.updated_at for row in rows}

    async def mark_completed(self, user_id: UUID, lesson_id: str, when: datetime) -> None:
        row = await self._session.get(LessonProgressModel, (user_id, lesson_id))
        if row is None:
            self._session.add(
                LessonProgressModel(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    status="completed",
                    updated_at=when,
                )
            )
            return
        row.updated_at = when

    async def reviewed_on(self, user_id: UUID, day: date) -> bool:
        row = await self._session.get(StudyCheckinModel, (user_id, day))
        return row is not None

    async def mark_reviewed(self, user_id: UUID, day: date) -> None:
        if await self.reviewed_on(user_id, day):
            return
        self._session.add(StudyCheckinModel(user_id=user_id, reviewed_on=day))
