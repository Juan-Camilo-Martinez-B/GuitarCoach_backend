"""Usuario del tutor."""

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.constants import MAX_LATENCY_OFFSET_MS, MIN_LATENCY_OFFSET_MS, SKILL_LEVELS
from app.domain.errors import InvalidValueError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    display_name: str
    level: str
    password_hash: str | None
    oauth_subject: str | None
    latency_offset_ms: int
    created_at: datetime

    def __post_init__(self) -> None:
        if _EMAIL.fullmatch(self.email) is None:
            raise InvalidValueError("El correo no tiene un formato válido.")
        if not self.display_name.strip():
            raise InvalidValueError("El nombre no puede estar vacío.")
        if self.level not in SKILL_LEVELS:
            raise InvalidValueError("El nivel no está permitido.")
        if self.password_hash is None and self.oauth_subject is None:
            raise InvalidValueError("El usuario necesita contraseña u OAuth.")
        if not MIN_LATENCY_OFFSET_MS <= self.latency_offset_ms <= MAX_LATENCY_OFFSET_MS:
            raise InvalidValueError("La calibración de latencia está fuera de rango.")
