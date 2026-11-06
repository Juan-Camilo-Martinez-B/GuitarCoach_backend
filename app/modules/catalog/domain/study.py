"""Dos caminos de una misma canción: acordes con rasgueo, y notas de la melodía."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StudyStep:
    bar: int
    beat: float
    symbol: str
    label: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "bar": self.bar,
            "beat": self.beat,
            "symbol": self.symbol,
            "label": self.label,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class StudyPlan:
    summary: str
    difficulty: str
    chords: tuple[StudyStep, ...]
    melody: tuple[StudyStep, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "difficulty": self.difficulty,
            "chords": [step.as_dict() for step in self.chords],
            "melody": [step.as_dict() for step in self.melody],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> StudyPlan:
        return cls(
            summary=str(raw["summary"]),
            difficulty=str(raw["difficulty"]),
            chords=_steps(raw.get("chords")),
            melody=_steps(raw.get("melody")),
        )


def _steps(value: object) -> tuple[StudyStep, ...]:
    if not isinstance(value, list):
        return ()
    steps: list[StudyStep] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        steps.append(
            StudyStep(
                bar=int(item["bar"]),
                beat=float(item["beat"]),
                symbol=str(item["symbol"]),
                label=str(item["label"]),
                detail=str(item["detail"]),
            )
        )
    return tuple(steps)
