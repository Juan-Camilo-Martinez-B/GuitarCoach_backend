"""Arma el análisis a partir del módulo alcanzado. Gemini puede reescribirlo después."""

import json

from app.domain.curriculum import LESSONS, review_lessons
from app.domain.entities.report import ReportContent
from app.domain.errors import InvalidValueError

MODES = ("quiz", "progresion")


def local_brief(mode: str, done: set[str]) -> ReportContent:
    if mode not in MODES:
        raise InvalidValueError("El modo de análisis no existe.")
    finished = review_lessons(done)
    nxt = next((lesson for lesson in LESSONS if lesson.id not in done), None)
    focus = nxt or (finished[-1] if finished else LESSONS[0])
    reached = finished[-1].title if finished else "ningún módulo"
    if mode == "quiz":
        return ReportContent(
            diagnostico=f"Llevas hasta {reached}. El quiz sale de {focus.title}.",
            ejercicios=_questions(focus.points),
            plan_semanal=(
                "Responde el quiz en voz alta antes de tomar la guitarra.",
                f"Después practica solo {focus.title}.",
                "Si fallas una respuesta, vuelve a ese punto y no avances.",
            ),
            consejos_tecnica=focus.points[:3],
        )
    chords = _progression(done)
    return ReportContent(
        diagnostico=(
            f"Tu progresión de hoy sale de {reached}. Tócala entera antes de una canción."
        ),
        ejercicios=tuple(
            f"Compás {index + 1}: {chord}, cuatro tiempos." for index, chord in enumerate(chords)
        ),
        plan_semanal=(
            "Dos vueltas lentas y una al tempo del módulo.",
            "Si un cambio se traba, aíslalo diez veces.",
            "Recién después abre la canción del módulo.",
        ),
        consejos_tecnica=focus.points[:3],
    )


def coach_prompt(mode: str, done: set[str], brief: ReportContent) -> str:
    payload = {
        "modo": mode,
        "modulos_completos": sorted(done),
        "borrador": {
            "diagnostico": brief.diagnostico,
            "ejercicios": list(brief.ejercicios),
            "plan_semanal": list(brief.plan_semanal),
            "consejos_tecnica": list(brief.consejos_tecnica),
        },
    }
    return (
        "Eres profesor de guitarra. Reescribe el borrador según el progreso real. "
        "No inventes módulos que no estén en la lista. Responde solo JSON con "
        "diagnostico, ejercicios, plan_semanal y consejos_tecnica.\n"
        f"DATOS:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _questions(points: tuple[str, ...]) -> tuple[str, ...]:
    questions = tuple(f"¿Puedes explicarlo sin mirar? {point}" for point in points[:3])
    if len(questions) >= 3:
        return questions
    return questions + ("Nombra la cuerda 1 y la cuerda 6.",) * (3 - len(questions))


def _progression(done: set[str]) -> tuple[str, ...]:
    if "cancion-lamento" in done or "rasgueo" in done:
        return ("Em", "D", "C", "G")
    if "abiertos" in done or "cancion-abiertos" in done:
        return ("G", "D", "Em", "C")
    if "notas" in done:
        return ("E", "A", "D", "G")
    return ("E", "A", "D")
