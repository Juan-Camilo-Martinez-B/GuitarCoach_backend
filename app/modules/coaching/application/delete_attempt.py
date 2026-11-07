"""Borra un intento y, con él, el informe que se armó a partir de ese intento."""

from uuid import UUID

from app.modules.coaching.ports import CoachingStore
from app.shared.errors import NotFoundError


class DeleteAttempt:
    def __init__(self, uow: CoachingStore) -> None:
        self._uow = uow

    async def execute(self, user_id: UUID, attempt_id: UUID) -> None:
        # El intento ajeno responde igual que el que no existe.
        attempt = await self._uow.attempts.get(attempt_id)
        if attempt is None or attempt.user_id != user_id:
            raise NotFoundError("El intento no existe.")
        await self._uow.reports.delete_for_attempt(attempt_id)
        await self._uow.attempts.delete(attempt_id)
        await self._uow.commit()
