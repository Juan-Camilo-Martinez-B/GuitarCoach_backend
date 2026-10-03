"""Resultado de un acorde esperado frente a lo que se detectó."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.constants import DEFAULT_HIT_WINDOW_MS
from app.domain.value_objects.chord import Chord


class HitKind(StrEnum):
    HIT = "hit"
    MISS = "miss"
    OMISSION = "omission"


@dataclass(frozen=True, slots=True)
class HitResult:
    expected: Chord
    detected: Chord | None
    delta_ms: int
    kind: HitKind
    bar: int = 1
    confidence: float = 1.0

    @classmethod
    def judge(
        cls,
        expected: Chord,
        detected: Chord | None,
        delta_ms: int,
        window_ms: int = DEFAULT_HIT_WINDOW_MS,
    ) -> HitResult:
        """Acierto solo si el símbolo coincide y el desfase cabe en la ventana."""
        if detected is None:
            kind = HitKind.OMISSION
        elif detected.symbol == expected.symbol and abs(delta_ms) <= window_ms:
            kind = HitKind.HIT
        else:
            kind = HitKind.MISS
        return cls(expected=expected, detected=detected, delta_ms=delta_ms, kind=kind)
