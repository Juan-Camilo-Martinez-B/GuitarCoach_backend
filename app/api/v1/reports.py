"""Informe del tutor para un intento."""

from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.v1.attempts import _bearer_user_id
from app.application.security import SystemClock
from app.application.use_cases.create_report import CreateReport
from app.core.config import Settings
from app.domain.entities.report import Report
from app.domain.errors import NotFoundError
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.ai.gemini_tutor import GeminiTutor

router = APIRouter(tags=["reports"])


class ReportResponse(BaseModel):
    id: str
    attempt_id: str
    diagnostico: str
    ejercicios: list[str]
    plan_semanal: list[str]
    consejos_tecnica: list[str]
    model: str


def _response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=str(report.id),
        attempt_id=str(report.attempt_id),
        diagnostico=report.content.diagnostico,
        ejercicios=list(report.content.ejercicios),
        plan_semanal=list(report.content.plan_semanal),
        consejos_tecnica=list(report.content.consejos_tecnica),
        model=report.model,
    )


@router.post("/attempts/{attempt_id}/report", status_code=201)
async def create_report(
    attempt_id: UUID,
    request: Request,
    authorization: str = Header(),
) -> ReportResponse:
    settings: Settings = request.app.state.settings
    uow: UnitOfWork = request.app.state.uow
    user_id = _bearer_user_id(authorization, settings)
    tutor = request.app.state.tutor
    if not isinstance(tutor, GeminiTutor) and not hasattr(tutor, "advise"):
        raise RuntimeError("El tutor no está configurado.")
    report = await CreateReport(uow, tutor, SystemClock(), settings.daily_report_limit).execute(
        user_id,
        attempt_id,
        "beginner",
    )
    return _response(report)


@router.get("/attempts/{attempt_id}/report")
async def get_report(attempt_id: UUID, request: Request) -> ReportResponse:
    uow: UnitOfWork = request.app.state.uow
    report = await uow.reports.get_by_attempt(attempt_id)
    if report is None:
        raise NotFoundError("El informe todavía no está listo.")
    return _response(report)
