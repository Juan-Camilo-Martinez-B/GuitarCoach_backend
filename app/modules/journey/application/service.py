"""Lee y actualiza el diario. Lo que la cuenta ya demuestra también cumple pasos y suma días."""

from collections.abc import Iterable
from datetime import date, timedelta
from uuid import UUID

from app.modules.journey.domain.journey import JourneySnapshot, snapshot
from app.modules.journey.ports import JourneyStore
from app.shared.clock import Clock

# La fecha la manda el navegador porque la racha sigue el día local del alumno. Solo se acepta
# dentro de los husos horarios reales; un reloj mal puesto no inventa días.
MAX_CLOCK_SKEW = timedelta(days=1)
# Hasta dónde se aceptan días guardados en el navegador antes de crear la cuenta.
MAX_HISTORY = timedelta(days=400)
FIRST_CHORD_LESSON = "acorde"


class JourneyService:
    def __init__(self, uow: JourneyStore, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def read(self, user_id: UUID, client_today: date) -> JourneySnapshot:
        today = self._safe_today(client_today)
        milestones = await self._uow.journey.milestones(user_id)
        days = await self._uow.journey.days(user_id)
        attempts = await self._uow.attempts.list_for_user(user_id)
        lessons = await self._uow.lessons.completed(user_id)
        guides = await self._uow.guides.list_for_owner(user_id)
        if attempts:
            milestones.add("tocar")
        if guides:
            milestones.add("propia")
        if FIRST_CHORD_LESSON in lessons:
            milestones.add("acorde")
        days.update(attempt.created_at.date() for attempt in attempts)
        days.update(when.date() for when in lessons.values())
        return snapshot(milestones, (day for day in days if day <= today), today)

    async def record(
        self,
        user_id: UUID,
        client_today: date,
        milestones: Iterable[str],
        days: Iterable[date],
    ) -> JourneySnapshot:
        """Es idempotente: repetir el aviso no cambia nada, así el navegador puede reintentar."""
        today = self._safe_today(client_today)
        oldest = today - MAX_HISTORY
        await self._uow.journey.add_milestones(user_id, set(milestones), self._clock.now())
        await self._uow.journey.add_days(user_id, {day for day in days if oldest <= day <= today})
        await self._uow.commit()
        return await self.read(user_id, today)

    def _safe_today(self, client_today: date) -> date:
        server_today = self._clock.now().date()
        return min(max(client_today, server_today - MAX_CLOCK_SKEW), server_today + MAX_CLOCK_SKEW)
