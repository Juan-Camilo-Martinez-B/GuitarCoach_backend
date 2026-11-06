"""Tempo de práctica."""

from dataclasses import dataclass

from app.shared.constants import MAX_BPM, MIN_BPM
from app.shared.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class Bpm:
    value: int

    def __post_init__(self) -> None:
        if not MIN_BPM <= self.value <= MAX_BPM:
            raise InvalidValueError(f"El tempo debe estar entre {MIN_BPM} y {MAX_BPM} BPM.")
