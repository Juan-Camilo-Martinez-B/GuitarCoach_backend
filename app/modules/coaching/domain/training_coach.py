"""Arma el análisis a partir del módulo alcanzado. Groq puede reescribirlo después."""

import json

from app.modules.coaching.domain.report import ReportContent
from app.modules.learning.public import LESSONS, review_lessons
from app.shared.errors import InvalidValueError

MODES = ("quiz", "progresion")
LOCAL_MODEL = "analisis-local"
# Hasta este desfase medio el alumno entra a tiempo.
ON_TIME_MS = 80.0


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


def local_report(
    song_title: str,
    accuracy: float,
    avg_delta_ms: float,
    weak_chords: tuple[str, ...],
) -> ReportContent:
    """El informe sin modelo externo: reglas simples sobre las métricas reales del intento."""
    score = round(accuracy)
    timing = (
        "Entras a tiempo."
        if abs(avg_delta_ms) <= ON_TIME_MS
        else f"Tus cambios se desvían unos {round(abs(avg_delta_ms))} ms del pulso."
    )
    focus = ", ".join(weak_chords[:3])
    return ReportContent(
        diagnostico=f"En {song_title} acertaste {score} % de los acordes. {timing}",
        ejercicios=(
            f"Repite el cambio hacia {focus} diez veces, sin rasguear."
            if focus
            else "Toca la canción completa una vez más para afianzarla.",
            "Toca la carta a la mitad de la velocidad, sin detenerte.",
            "Sube la velocidad solo cuando aciertes dos vueltas seguidas.",
        ),
        plan_semanal=(
            "Día 1 y 2: cambios lentos entre los acordes de la canción.",
            "Día 3 y 4: la carta completa a velocidad media.",
            "Día 5: la canción a su velocidad y un intento nuevo para comparar.",
        ),
        consejos_tecnica=(
            "Mira la siguiente forma antes de soltar la actual.",
            "Pisa justo detrás del metal del traste, sin apretar de más.",
            "Mantén la mano del rasgueo en movimiento, aunque cambies tarde.",
        ),
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
