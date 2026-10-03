"""Frecuencia en hertz, inmutable."""

from dataclasses import dataclass

from app.domain.constants import MAX_HERTZ, MIN_HERTZ
from app.domain.errors import InvalidValueError


@dataclass(frozen=True, slots=True)
class Frequency:
    """Una frecuencia audible positiva, dentro del rango que el dominio acepta."""

    hertz: float

    def __post_init__(self) -> None:
        if not MIN_HERTZ <= self.hertz <= MAX_HERTZ:
            raise InvalidValueError(
                f"La frecuencia debe estar entre {MIN_HERTZ:g} y {MAX_HERTZ:g} Hz."
            )
