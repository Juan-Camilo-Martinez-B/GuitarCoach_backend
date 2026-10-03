"""Trabajo de importación. El estado solo avanza por métodos, no por asignación libre."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from app.domain.constants import JOB_STATUSES
from app.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class ScrapeJob:
    id: UUID
    user_id: UUID | None
    song_id: int | None
    status: str
    query: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.status not in JOB_STATUSES:
            raise InvalidValueError("Estado de trabajo desconocido.")
        if not self.query.strip():
            raise InvalidValueError("La búsqueda del trabajo no puede estar vacía.")
        if self.status == "failed" and not (self.error and self.error.strip()):
            raise InvalidValueError("Un trabajo fallido necesita el motivo.")

    def mark_running(self, now: datetime) -> ScrapeJob:
        return replace(self, status="running", error=None, updated_at=now)

    def mark_done(self, song_id: int, now: datetime) -> ScrapeJob:
        return replace(self, status="done", song_id=song_id, error=None, updated_at=now)

    def mark_failed(self, reason: str, now: datetime) -> ScrapeJob:
        return replace(self, status="failed", error=reason, updated_at=now)
