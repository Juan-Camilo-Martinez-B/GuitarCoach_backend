"""La ruta del principiante: pasos cumplidos, días de práctica y los logros que salen de ellos."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

MILESTONES = ("afinar", "acorde", "tocar", "propia", "avance")
THREE_DAYS = 3


@dataclass(frozen=True, slots=True)
class JourneySnapshot:
    milestones: tuple[str, ...]
    days: tuple[date, ...]
    current_streak: int
    best_streak: int
    badges: tuple[str, ...]


def streaks(days: Iterable[date], today: date) -> tuple[int, int]:
    """La racha viva y la mejor. La racha sigue viva si el último día fue hoy o ayer."""
    ordered = sorted(set(days))
    best = 0
    run = 0
    previous: date | None = None
    for day in ordered:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    alive = previous is not None and today - previous <= timedelta(days=1)
    return (run if alive else 0), best


def earned_badges(milestones: Iterable[str], best_streak: int) -> tuple[str, ...]:
    done = set(milestones)
    rules = (
        ("buen-oido", "afinar" in done),
        ("primer-acorde", "acorde" in done),
        ("primera-cancion", "tocar" in done),
        ("mi-cancion", "propia" in done),
        ("tres-dias", best_streak >= THREE_DAYS),
        ("ruta-completa", done.issuperset(MILESTONES)),
    )
    return tuple(badge for badge, won in rules if won)


def snapshot(milestones: Iterable[str], days: Iterable[date], today: date) -> JourneySnapshot:
    done = tuple(step for step in MILESTONES if step in set(milestones))
    unique = tuple(sorted(set(days)))
    current, best = streaks(unique, today)
    return JourneySnapshot(done, unique, current, best, earned_badges(done, best))
