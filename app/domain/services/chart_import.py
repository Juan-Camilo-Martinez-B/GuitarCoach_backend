"""Carta plana y plan de estudio a partir de una guía. Los lectores viven en guide_import."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.domain.entities.guide import SongGuide
from app.domain.entities.study import StudyPlan, StudyStep
from app.domain.services.guide_import import guide_from_file
from app.domain.value_objects.chord import Chord

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_SOLFEGE = {
    "C": "Do",
    "C#": "Do#",
    "D": "Re",
    "D#": "Re#",
    "E": "Mi",
    "F": "Fa",
    "F#": "Fa#",
    "G": "Sol",
    "G#": "Sol#",
    "A": "La",
    "A#": "La#",
    "B": "Si",
}
_FLATS = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
_OPEN = {"C", "D", "E", "Em", "G", "A", "Am", "Dm"}
_STRUM = ("abajo", "abajo", "arriba", "arriba", "abajo", "arriba")


@dataclass(frozen=True, slots=True)
class ImportedChart:
    title: str
    artist: str
    song_key: str | None
    bpm: int
    chords: tuple[tuple[int, float, str], ...]
    melody: tuple[tuple[int, float, str], ...]

    def digest(self) -> str:
        payload = {
            "title": self.title,
            "artist": self.artist,
            "chords": self.chords,
            "melody": self.melody,
        }
        raw = json.dumps(payload, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()


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


def build_plan(
    title: str,
    song_key: str | None,
    bpm: int,
    chords: tuple[tuple[int, float, str], ...],
    melody: tuple[tuple[int, float, str], ...] = (),
) -> StudyPlan:
    unique = tuple(dict.fromkeys(symbol for _, _, symbol in chords))
    difficulty = _difficulty(unique)
    key = song_key or "sin indicar"
    summary = (
        f"{title}: {len(chords)} cambios, tonalidad {key}, {bpm} BPM. Dificultad {difficulty}."
    )
    chord_steps = tuple(
        StudyStep(bar, beat, symbol, symbol, f"rasgueo {_STRUM[index % len(_STRUM)]}")
        for index, (bar, beat, symbol) in enumerate(chords)
    )
    if melody:
        melody_steps = tuple(
            StudyStep(bar, beat, note, solfege(note), "nota de la melodía")
            for bar, beat, note in melody
        )
    else:
        melody_steps = tuple(
            StudyStep(bar, beat, _root(symbol), solfege(_root(symbol)), "fundamental del acorde")
            for bar, beat, symbol in chords
        )
    return StudyPlan(summary, difficulty, chord_steps, melody_steps)


def solfege(symbol: str) -> str:
    return _SOLFEGE.get(_spell(symbol), symbol)


def _difficulty(symbols: tuple[str, ...]) -> str:
    if len(symbols) <= 4 and set(symbols).issubset(_OPEN):
        return "facil"
    if len(symbols) <= 6:
        return "media"
    return "exigente"


def _root(symbol: str) -> str:
    chord = Chord.parse(symbol)
    return _spell(f"{chord.root}{chord.accidental}")


def _spell(symbol: str) -> str:
    chord = Chord.parse(symbol) if len(symbol) > 2 or symbol not in _SOLFEGE else None
    if chord is None:
        return _FLATS.get(symbol, symbol)
    spelled = _FLATS.get(f"{chord.root}{chord.accidental}", f"{chord.root}{chord.accidental}")
    return spelled if spelled in _NAMES else symbol
