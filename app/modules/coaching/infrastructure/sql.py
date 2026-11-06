"""Repositorios SQLAlchemy. Traducen filas a entidades y al revés."""

from datetime import date
from uuid import UUID

from sqlalchemy import column, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.coaching.domain.report import Report, ReportContent
from app.modules.coaching.infrastructure.models import ReportModel

_ATTEMPTS = table("attempts", column("id"), column("user_id"))


class SqlReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: Report) -> None:
        self._session.add(
            ReportModel(
                id=report.id,
                attempt_id=report.attempt_id,
                content={
                    "diagnostico": report.content.diagnostico,
                    "ejercicios": list(report.content.ejercicios),
                    "plan_semanal": list(report.content.plan_semanal),
                    "consejos_tecnica": list(report.content.consejos_tecnica),
                },
                model=report.model,
                metrics_hash=report.metrics_hash,
                created_at=report.created_at,
            )
        )

    async def get_by_attempt(self, attempt_id: UUID) -> Report | None:
        row = await self._session.scalar(
            select(ReportModel).where(ReportModel.attempt_id == attempt_id)
        )
        return None if row is None else _report_to_entity(row)

    async def find_by_metrics_hash(self, metrics_hash: str) -> Report | None:
        row = await self._session.scalar(
            select(ReportModel).where(ReportModel.metrics_hash == metrics_hash)
        )
        return None if row is None else _report_to_entity(row)

    async def count_for_user_on_day(self, user_id: UUID, day: date) -> int:
        rows = await self._session.scalars(
            select(ReportModel)
            .join(_ATTEMPTS, _ATTEMPTS.c.id == ReportModel.attempt_id)
            .where(_ATTEMPTS.c.user_id == user_id)
        )
        return sum(1 for row in rows if row.created_at.date() == day)


def _text_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _report_to_entity(row: ReportModel) -> Report:
    content = row.content
    return Report(
        id=row.id,
        attempt_id=row.attempt_id,
        content=ReportContent(
            diagnostico=str(content["diagnostico"]),
            ejercicios=_text_list(content["ejercicios"]),
            plan_semanal=_text_list(content["plan_semanal"]),
            consejos_tecnica=_text_list(content["consejos_tecnica"]),
        ),
        model=row.model,
        metrics_hash=row.metrics_hash,
        created_at=row.created_at,
    )
