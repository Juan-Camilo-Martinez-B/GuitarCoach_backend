"""Desviación en cents entre dos frecuencias."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.constants import CENTS_PER_OCTAVE
from app.domain.value_objects.frequency import Frequency


@dataclass(frozen=True, slots=True)
class Cents:
    """100 cents son un semitono. El signo positivo significa que suena agudo."""

    value: float

    @classmethod
    def between(cls, actual: Frequency, target: Frequency) -> Cents:
        return cls(CENTS_PER_OCTAVE * math.log2(actual.hertz / target.hertz))
