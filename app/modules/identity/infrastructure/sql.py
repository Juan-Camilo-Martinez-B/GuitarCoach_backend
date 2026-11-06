"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.user import User
from app.modules.identity.infrastructure.models import UserModel


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                display_name=user.display_name,
                level=user.level,
                oauth_subject=user.oauth_subject,
                latency_offset_ms=user.latency_offset_ms,
                created_at=user.created_at,
            )
        )

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email.lower()))
        return None if row is None else _user_to_entity(row)

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return None if row is None else _user_to_entity(row)


def _user_to_entity(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        level=row.level,
        password_hash=row.password_hash,
        oauth_subject=row.oauth_subject,
        latency_offset_ms=row.latency_offset_ms,
        created_at=row.created_at,
    )
