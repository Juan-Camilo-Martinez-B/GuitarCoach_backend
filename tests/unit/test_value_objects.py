"""Conversiones de nota y reglas de los value objects."""

import math

import pytest
from app.domain.constants import A4_HERTZ, CENTS_PER_OCTAVE, SEMITONES_PER_OCTAVE
from app.domain.errors import InvalidValueError
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.cents import Cents
from app.domain.value_objects.chord import Chord
from app.domain.value_objects.frequency import Frequency
from app.domain.value_objects.hit_result import HitKind, HitResult
from app.domain.value_objects.note import Note


def test_el_la_440_es_la_nota_a4() -> None:
    note = Note.from_frequency(Frequency(A4_HERTZ))
    assert note.midi == 69
    assert note.name == "A4"


def test_un_semitono_por_encima_del_la_son_cien_cents() -> None:
    target = Note.from_frequency(Frequency(A4_HERTZ)).frequency
    actual = Frequency(A4_HERTZ * (2 ** (1 / SEMITONES_PER_OCTAVE)))
    cents = Cents.between(actual, target)
    assert math.isclose(cents.value, CENTS_PER_OCTAVE / SEMITONES_PER_OCTAVE, abs_tol=0.01)


def test_rechaza_frecuencia_y_tempo_fuera_de_rango() -> None:
    with pytest.raises(InvalidValueError):
        Frequency(0)
    with pytest.raises(InvalidValueError):
        Bpm(10)


def test_normaliza_el_simbolo_del_acorde() -> None:
    assert Chord.parse("F#m7").symbol == "F#m7"
    assert Chord.parse("Am").symbol == "Am"
    with pytest.raises(InvalidValueError):
        Chord.parse("H7")


def test_juzga_acierto_fallo_y_omision() -> None:
    expected = Chord.parse("Am")
    assert HitResult.judge(expected, Chord.parse("Am"), 40).kind is HitKind.HIT
    assert HitResult.judge(expected, Chord.parse("Am"), 400).kind is HitKind.MISS
    assert HitResult.judge(expected, Chord.parse("Em"), 20).kind is HitKind.MISS
    assert HitResult.judge(expected, None, 0).kind is HitKind.OMISSION
