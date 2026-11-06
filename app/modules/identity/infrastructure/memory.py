"""Adaptador en memoria para pruebas y para el proceso local antes de SQL."""

from uuid import UUID

from app.modules.identity.domain.user import User


class InMemoryUsers:
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        self._by_id[user.id] = user

    async def get_by_email(self, email: str) -> User | None:
        normalized = email.lower()
        return next((user for user in self._by_id.values() if user.email == normalized), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)
