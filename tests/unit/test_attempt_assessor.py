"""El resumen de un intento sale de los eventos, no de cifras enviadas por el cliente."""

import pytest
from app.domain.errors import InvalidValueError
from app.domain.services.attempt_assessor import AttemptAssessor
from app.domain.value_objects.chord import Chord
from app.domain.value_objects.hit_result import HitResult


def test_resume_precision_y_la_transicion_fallida() -> None:
    events = (
        HitResult.judge(Chord.parse("G"), Chord.parse("G"), 40),
        HitResult.judge(Chord.parse("C"), Chord.parse("Am"), 20),
    )
    assessment = AttemptAssessor().assess(events)
    assert assessment.accuracy == 50.0
    assert assessment.problematic_transitions == (("G", "C"),)
    by_chord = {metric.chord: metric for metric in assessment.chord_metrics}
    assert by_chord["C"].errors == 1
    assert by_chord["G"].accuracy == 100.0


def test_rechaza_un_intento_sin_eventos() -> None:
    with pytest.raises(InvalidValueError):
        AttemptAssessor().assess(())
