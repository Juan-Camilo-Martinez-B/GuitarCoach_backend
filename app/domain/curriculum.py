"""Módulos en orden. El progreso vive en la base; el temario no cambia por usuario."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    title: str
    summary: str
    points: tuple[str, ...]
    song_title: str | None = None


LESSONS: tuple[Lesson, ...] = (
    Lesson(
        "cuerdas",
        "Las cuerdas, del 1 al 6",
        "La numeración sale de la más aguda, no del orden en que las miras.",
        (
            "La cuerda 1 es la más fina y la más aguda. Al aire suena Mi.",
            "La cuerda 6 es la más gruesa y la más grave. Al aire suena Mi, dos octavas abajo.",
            "De la 6 a la 1, al aire: Mi, La, Re, Sol, Si, Mi.",
            "Con la guitarra en posición, la 6 queda arriba, cerca de la cara, y la 1 abajo.",
        ),
    ),
    Lesson(
        "trastes",
        "Los trastes y desde dónde se cuentan",
        "El número del traste se cuenta desde la cejuela hacia el cuerpo.",
        (
            "Los trastes son las tiras de metal que cruzan el diapasón.",
            "Se empiezan a contar en la cejuela, el huesito junto a las clavijas.",
            "El traste 1 es el primer espacio después de la cejuela.",
            "Al aire significa no pisar: el número es 0. El dedo va justo detrás del metal.",
        ),
    ),
    Lesson(
        "acorde",
        "Qué es un acorde",
        "Un acorde son varias notas a la vez, con un nombre que dice su base.",
        (
            "Rasguear varias cuerdas juntas forma un acorde.",
            "El nombre dice la fundamental: Sol se apoya en la nota Sol.",
            "La m lo hace menor: Mim suena más cerrado que Mi.",
            "Un cambio es soltar una forma y armar la siguiente a tiempo.",
        ),
    ),
    Lesson(
        "notas",
        "Do, Re, Mi, Fa, Sol, La, Si",
        "Estas siete notas alcanzan para las primeras melodías.",
        (
            "Do, Re, Mi, Fa, Sol, La, Si se escriben C, D, E, F, G, A, B.",
            "Al aire ya están Mi (cuerdas 6 y 1), La (5), Re (4), Sol (3) y Si (2).",
            "Do está en la cuerda 2, traste 1. Fa está en la cuerda 1, traste 1.",
            "Re también está en la cuerda 2, traste 3.",
        ),
    ),
    Lesson(
        "abiertos",
        "Acordes abiertos",
        "Cuatro formas alcanzan para las primeras canciones.",
        (
            "Mim: pisas la cuerda 5 en el traste 2 y la 4 en el traste 2.",
            "Sol: cuerda 6 traste 3, cuerda 5 traste 2, cuerda 1 traste 3.",
            "Do: cuerda 5 traste 3, cuerda 4 traste 2, cuerda 2 traste 1.",
            "Re: cuerda 3 traste 2, cuerda 2 traste 3, cuerda 1 traste 2. La 6 y la 5 no suenan.",
            "Lam: cuerda 2 traste 1, cuerda 4 traste 2, cuerda 3 traste 2.",
        ),
    ),
    Lesson(
        "rasgueo",
        "Rasgueo básico",
        "La mano marca el pulso antes de acelerar.",
        (
            "Abajo va de la cuerda 6 hacia la 1. Arriba vuelve.",
            "El patrón de la escuela es abajo, abajo, arriba, arriba, abajo, arriba.",
            "Se mueve la muñeca. El antebrazo casi quieto.",
            "Primero lento y parejo. La velocidad llega después del pulso.",
        ),
    ),
    Lesson(
        "cancion-abiertos",
        "Canción: Cambios abiertos",
        "Cuatro acordes mayores y menores, sin prisa.",
        (
            "La carta es Sol, Re, Mim y Do, a 72 BPM.",
            "En acordes, rasguea cada forma cuando cambia el cuadro.",
            "En notas, canta la fundamental: Sol, Re, Mi, Do.",
        ),
        "Cambios abiertos",
    ),
    Lesson(
        "cancion-menores",
        "Canción: Ronda de menores",
        "Una vuelta corta en Lam para afirmar el cambio.",
        (
            "La carta es Lam, Rem, Mi y Lam, a 66 BPM.",
            "Deja sonar el acorde un compás entero antes de moverte.",
            "En notas, la línea es La, Re, Mi, La.",
        ),
        "Ronda de menores",
    ),
    Lesson(
        "cancion-lamento",
        "Canción: Lamento boliviano",
        "La armonía de la canción, en su tempo, sin la letra.",
        (
            "Va a 124 BPM, el tempo de la canción, en compás de cuatro.",
            "La armonía es Mim, Sim7, Lam y, en el último compás, Mim y Si7. Sim7 va sin cejilla.",
            "El primer rasgueo dura un tiempo; los cinco siguientes, medio tiempo.",
            "No incluye la letra. En notas: Mi, Si, La, Mi, Si.",
        ),
        "Lamento boliviano",
    ),
)


def lesson_by_id(lesson_id: str) -> Lesson | None:
    return next((lesson for lesson in LESSONS if lesson.id == lesson_id), None)


def previous_id(lesson_id: str) -> str | None:
    for index, lesson in enumerate(LESSONS):
        if lesson.id == lesson_id:
            return None if index == 0 else LESSONS[index - 1].id
    return None


def review_lessons(done: set[str]) -> tuple[Lesson, ...]:
    finished = tuple(lesson for lesson in LESSONS if lesson.id in done)
    return finished[-2:]
