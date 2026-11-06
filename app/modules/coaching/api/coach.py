"""Quiz o progresión según el módulo alcanzado."""

from typing import cast

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.modules.coaching.application.coach import CoachStudent
from app.modules.coaching.ports import CoachingStore, Tutor
from app.modules.identity.public import bearer_user_id
from app.shared.http.deps import current_settings, current_uow

router = APIRouter(tags=["lessons"])


class CoachBody(BaseModel):
    mode: str


class CoachView(BaseModel):
    diagnostico: str
    ejercicios: list[str]
    plan_semanal: list[str]
    consejos_tecnica: list[str]
    model: str


@router.post("/me/coach")
async def coach(
    body: CoachBody,
    request: Request,
    authorization: str = Header(),
) -> CoachView:
    settings = current_settings(request)
    user_id = bearer_user_id(authorization, settings)
    advice = await CoachStudent(
        cast(CoachingStore, current_uow(request)),
        cast(Tutor, request.app.state.tutor),
        settings.groq_model,
        bool(settings.groq_api_key.strip()),
    ).execute(user_id, body.mode)
    return CoachView(
        diagnostico=advice.content.diagnostico,
        ejercicios=list(advice.content.ejercicios),
        plan_semanal=list(advice.content.plan_semanal),
        consejos_tecnica=list(advice.content.consejos_tecnica),
        model=advice.model,
    )
