"""Nota MIDI y su nombre. La conversión usa el la 440."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.constants import A4_HERTZ, A4_MIDI, NOTE_NAMES, SEMITONES_PER_OCTAVE
from app.domain.errors import InvalidValueError
from app.domain.value_objects.frequency import Frequency

MIN_MIDI = 0
MAX_MIDI = 127


@dataclass(frozen=True, slots=True)
class Note:
    """Nota temperada. El nombre sale del número MIDI, no de una cadena libre."""

    midi: int

    def __post_init__(self) -> None:
        if not MIN_MIDI <= self.midi <= MAX_MIDI:
            raise InvalidValueError("La nota MIDI está fuera de 0..127.")

    @property
    def name(self) -> str:
        octave = (self.midi // SEMITONES_PER_OCTAVE) - 1
        return f"{NOTE_NAMES[self.midi % SEMITONES_PER_OCTAVE]}{octave}"

    @property
    def frequency(self) -> Frequency:
        hertz = A4_HERTZ * (2 ** ((self.midi - A4_MIDI) / SEMITONES_PER_OCTAVE))
        return Frequency(hertz)

    @classmethod
    def from_frequency(cls, frequency: Frequency) -> Note:
        """Redondea al semitono más cercano."""
        midi = round(A4_MIDI + SEMITONES_PER_OCTAVE * math.log2(frequency.hertz / A4_HERTZ))
        return cls(int(midi))
