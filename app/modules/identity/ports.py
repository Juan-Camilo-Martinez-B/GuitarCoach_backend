"""Puertos de identidad. La infraestructura los implementa."""

from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.user import User
from app.shared.persistence.transaction import Transactional


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...


class IdentityStore(Transactional, Protocol):
    users: UserRepository
