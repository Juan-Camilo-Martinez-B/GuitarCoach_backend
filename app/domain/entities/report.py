"""Informe del tutor. El contenido ya está validado antes de llegar aquí."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class ReportContent:
    diagnostico: str
    ejercicios: tuple[str, ...]
    plan_semanal: tuple[str, ...]
    consejos_tecnica: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.diagnostico.strip():
            raise InvalidValueError("El diagnóstico no puede estar vacío.")
        if not self.ejercicios or not self.plan_semanal or not self.consejos_tecnica:
            raise InvalidValueError("El informe necesita ejercicios, plan y consejos.")


@dataclass(frozen=True, slots=True)
class Report:
    id: UUID
    attempt_id: UUID
    content: ReportContent
    model: str
    metrics_hash: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.metrics_hash.strip():
            raise InvalidValueError("El informe necesita modelo y hash de métricas.")
