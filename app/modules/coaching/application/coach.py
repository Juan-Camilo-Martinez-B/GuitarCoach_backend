"""El análisis según el curso. Si el tutor externo falla, vale el análisis local."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.coaching.domain.report import ReportContent
from app.modules.coaching.domain.training_coach import (
    LOCAL_MODEL,
    MODES,
    coach_prompt,
    local_brief,
)
from app.modules.coaching.ports import CoachingStore, Tutor
from app.shared.errors import ExternalServiceError, NotFoundError


@dataclass(frozen=True, slots=True)
class CoachAdvice:
    content: ReportContent
    model: str


class CoachStudent:
    def __init__(self, uow: CoachingStore, tutor: Tutor, model: str, tutor_ready: bool) -> None:
        self._uow = uow
        self._tutor = tutor
        self._model = model
        self._tutor_ready = tutor_ready

    async def execute(self, user_id: UUID, mode: str) -> CoachAdvice:
        if mode not in MODES:
            raise NotFoundError("El modo de análisis no existe.")
        done = set((await self._uow.lessons.completed(user_id)).keys())
        brief = local_brief(mode, done)
        if not self._tutor_ready:
            return CoachAdvice(brief, LOCAL_MODEL)
        try:
            advised = await self._tutor.advise(coach_prompt(mode, done, brief))
        except ExternalServiceError:
            return CoachAdvice(brief, LOCAL_MODEL)
        return CoachAdvice(advised, self._model)
