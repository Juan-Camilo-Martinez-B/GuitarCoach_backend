"""Intento de práctica y su métrica por acorde."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.constants import MAX_ACCURACY, MIN_ACCURACY
from app.domain.errors import InvalidValueError
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.hit_result import HitResult


@dataclass(frozen=True, slots=True)
class ChordMetric:
    chord: str
    accuracy: float
    avg_delta_ms: float
    errors: int
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.chord.strip():
            raise InvalidValueError("La métrica necesita un acorde.")
        if not MIN_ACCURACY <= self.accuracy <= MAX_ACCURACY:
            raise InvalidValueError("La precisión de la métrica está fuera de 0..100.")
        if self.errors < 0:
            raise InvalidValueError("Los errores no pueden ser negativos.")


@dataclass(frozen=True, slots=True)
class Attempt:
    id: UUID
    user_id: UUID
    song_id: int
    bpm: Bpm
    accuracy: float
    avg_delta_ms: float
    latency_offset_ms: int
    tuning_cents_avg: float | None
    events: tuple[HitResult, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not MIN_ACCURACY <= self.accuracy <= MAX_ACCURACY:
            raise InvalidValueError("La precisión del intento está fuera de 0..100.")
        if self.song_id < 1:
            raise InvalidValueError("El intento debe apuntar a una canción.")
