"""Agrega los aciertos de un intento. El cálculo vive en el dominio, no en el controlador."""

from collections import defaultdict
from dataclasses import dataclass

from app.domain.errors import InvalidValueError
from app.domain.value_objects.hit_result import HitKind, HitResult


@dataclass(frozen=True, slots=True)
class ChordSummary:
    chord: str
    accuracy: float
    avg_delta_ms: float
    errors: int


@dataclass(frozen=True, slots=True)
class AttemptAssessment:
    accuracy: float
    avg_delta_ms: float
    chord_metrics: tuple[ChordSummary, ...]
    problematic_transitions: tuple[tuple[str, str], ...]


class AttemptAssessor:
    """Precisión global, precisión por acorde y transiciones donde el destino falló."""

    def assess(self, events: tuple[HitResult, ...] | list[HitResult]) -> AttemptAssessment:
        if not events:
            raise InvalidValueError("El intento no trae eventos.")
        hits = sum(1 for event in events if event.kind is HitKind.HIT)
        accuracy = round(100.0 * hits / len(events), 2)
        played = [event.delta_ms for event in events if event.kind is not HitKind.OMISSION]
        avg_delta = round(sum(played) / len(played), 2) if played else 0.0
        grouped: dict[str, list[HitResult]] = defaultdict(list)
        for event in events:
            grouped[event.expected.symbol].append(event)
        metrics = tuple(self._summarize(symbol, group) for symbol, group in sorted(grouped.items()))
        transitions = tuple(
            (previous.expected.symbol, current.expected.symbol)
            for previous, current in zip(events, events[1:], strict=False)
            if current.kind is not HitKind.HIT
        )
        return AttemptAssessment(accuracy, avg_delta, metrics, transitions)

    def _summarize(self, symbol: str, group: list[HitResult]) -> ChordSummary:
        group_hits = sum(1 for event in group if event.kind is HitKind.HIT)
        played = [event.delta_ms for event in group if event.kind is not HitKind.OMISSION]
        avg_delta = round(sum(played) / len(played), 2) if played else 0.0
        errors = sum(1 for event in group if event.kind is not HitKind.HIT)
        return ChordSummary(
            chord=symbol,
            accuracy=round(100.0 * group_hits / len(group), 2),
            avg_delta_ms=avg_delta,
            errors=errors,
        )
