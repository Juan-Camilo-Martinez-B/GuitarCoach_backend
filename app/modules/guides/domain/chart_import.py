"""Carta plana a partir de una guía. Los lectores viven en guide_import."""

from __future__ import annotations

from app.modules.catalog.public import ImportedChart
from app.modules.guides.domain.guide import SongGuide
from app.modules.guides.domain.guide_import import guide_from_file

_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def parse_chart(filename: str, raw: bytes) -> ImportedChart:
    guide, _ = guide_from_file(filename, raw)
    return imported_from_guide(guide)


def imported_from_guide(guide: SongGuide) -> ImportedChart:
    """La carta plana (compás y pulso desde 1) que usan el estudio y la práctica."""
    chords = tuple((chord.bar, chord.beat, chord.chord.symbol) for chord in guide.chart())
    melody = tuple(
        (
            int(note.start // guide.beats_per_bar) + 1,
            round(note.start % guide.beats_per_bar, 4) + 1,
            _NAMES[note.midi % 12],
        )
        for note in guide.melody
    )
    return ImportedChart(guide.title, guide.artist, guide.song_key, guide.bpm.value, chords, melody)
