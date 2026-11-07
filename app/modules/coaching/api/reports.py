"""Informe del tutor para un intento."""

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel

from app.modules.coaching.application.create_report import CreateReport
from app.modules.coaching.application.delete_attempt import DeleteAttempt
from app.modules.coaching.domain.report import Report
from app.modules.coaching.ports import CoachingStore, Tutor
from app.modules.identity.public import bearer_user_id
from app.shared.clock import SystemClock
from app.shared.errors import NotFoundError
from app.shared.http.deps import current_settings, current_uow

router = APIRouter(tags=["reports"])


class ReportResponse(BaseModel):
    id: str
    attempt_id: str
    diagnostico: str
    ejercicios: list[str]
    plan_semanal: list[str]
    consejos_tecnica: list[str]
    model: str


def _store(request: Request) -> CoachingStore:
    return cast(CoachingStore, current_uow(request))


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
    settings = current_settings(request)
    uow = _store(request)
    user_id = bearer_user_id(authorization, settings)
    tutor = cast(Tutor, request.app.state.tutor)
    report = await CreateReport(uow, tutor, SystemClock(), settings.daily_report_limit).execute(
        user_id,
        attempt_id,
        "beginner",
    )
    return _response(report)


@router.delete("/attempts/{attempt_id}", status_code=204)
async def delete_attempt(
    attempt_id: UUID,
    request: Request,
    authorization: str = Header(),
) -> Response:
    """Borra el intento del alumno. El informe y las métricas se van con él."""
    user_id = bearer_user_id(authorization, current_settings(request))
    await DeleteAttempt(_store(request)).execute(user_id, attempt_id)
    return Response(status_code=204)


@router.get("/attempts/{attempt_id}/report")
async def get_report(
    attempt_id: UUID,
    request: Request,
    authorization: str = Header(),
) -> ReportResponse:
    uow = _store(request)
    user_id = bearer_user_id(authorization, current_settings(request))
    attempt = await uow.attempts.get(attempt_id)
    # El informe ajeno responde igual que el que no existe.
    report = None
    if attempt is not None and attempt.user_id == user_id:
        report = await uow.reports.get_by_attempt(attempt_id)
    if report is None:
        raise NotFoundError("El informe todavía no está listo.")
    return _response(report)
