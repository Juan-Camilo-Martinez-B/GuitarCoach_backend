"""Ruta guiada, racha y logros de la cuenta."""

from datetime import date
from typing import Literal, cast

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.modules.identity.public import bearer_user_id
from app.modules.journey.application.service import JourneyService
from app.modules.journey.domain.journey import JourneySnapshot
from app.modules.journey.ports import JourneyStore
from app.shared.clock import SystemClock
from app.shared.http.deps import current_settings, current_uow

router = APIRouter(tags=["journey"])

Milestone = Literal["afinar", "acorde", "tocar", "propia", "avance"]
# Los días guardados en el navegador durante un año, más un margen.
MAX_DAYS_PER_REQUEST = 400


class JourneyBody(BaseModel):
    today: date
    milestones: list[Milestone] = Field(default_factory=list, max_length=5)
    days: list[date] = Field(default_factory=list, max_length=MAX_DAYS_PER_REQUEST)


class JourneyView(BaseModel):
    milestones: list[str]
    days: list[date]
    current_streak: int
    best_streak: int
    badges: list[str]


def _service(request: Request) -> JourneyService:
    return JourneyService(cast(JourneyStore, current_uow(request)), SystemClock())


def _view(state: JourneySnapshot) -> JourneyView:
    return JourneyView(
        milestones=list(state.milestones),
        days=list(state.days),
        current_streak=state.current_streak,
        best_streak=state.best_streak,
        badges=list(state.badges),
    )


@router.get("/me/journey")
async def read_journey(
    request: Request,
    today: date,
    authorization: str = Header(),
) -> JourneyView:
    user_id = bearer_user_id(authorization, current_settings(request))
    return _view(await _service(request).read(user_id, today))


@router.post("/me/journey")
async def record_journey(
    body: JourneyBody,
    request: Request,
    authorization: str = Header(),
) -> JourneyView:
    user_id = bearer_user_id(authorization, current_settings(request))
    state = await _service(request).record(user_id, body.today, body.milestones, body.days)
    return _view(state)
