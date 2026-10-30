"""Guía de estudio de una canción: secciones, acordes con duración, rasgueo y melodía.

El tiempo se cuenta en pulsos de negra desde el inicio de la canción (el primero es 0).
La guía nunca guarda la letra.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.song import ChartChord
from app.domain.errors import InvalidValueError
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord

GUIDE_VERSION = 1
SOURCE_KINDS = ("pegado", "chordpro", "musicxml", "audio", "editor")
STATUSES = ("borrador", "revisada")
STRUM_DIRECTIONS = ("abajo", "arriba", "apagado")
MAX_SECTIONS = 40
MAX_CHORDS = 2000
MAX_NOTES = 4000
MAX_TEXT = 120
MIN_MIDI = 28
MAX_MIDI = 100
_STRUM_LETTERS = {
    "D": "abajo",
    "B": "abajo",
    "↓": "abajo",
    "U": "arriba",
    "S": "arriba",
    "↑": "arriba",
    "X": "apagado",
    "×": "apagado",
}
_STRUM_RESTS = {"-", "."}
_EPSILON = 1e-6


def _text(value: object, field: str, *, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise InvalidValueError(f"Falta {field}.")
    if len(text) > MAX_TEXT:
        raise InvalidValueError(f"{field} supera {MAX_TEXT} caracteres.")
    return text


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidValueError(f"{field} debe ser un número.")
    return float(value)


def _time(value: float) -> float:
    """Tiempos siempre como float y redondeados: 0 y 0.0 deben dar el mismo hash."""
    return round(float(value), 6)


def _items(value: object, field: str, limit: int) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise InvalidValueError(f"{field} debe ser una lista de objetos.")
    if len(value) > limit:
        raise InvalidValueError(f"{field} supera el máximo de {limit}.")
    return value


@dataclass(frozen=True, slots=True)
class StrumPattern:
    """Golpes de un compás, cada uno con lo que dura hasta el siguiente."""

    directions: tuple[str, ...]
    beats: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.directions or len(self.directions) != len(self.beats):
            raise InvalidValueError("El rasgueo necesita un golpe por duración.")
        if any(direction not in STRUM_DIRECTIONS for direction in self.directions):
            raise InvalidValueError("El rasgueo solo admite abajo, arriba y apagado.")
        if any(beat <= 0 for beat in self.beats) or sum(self.beats) > 16:
            raise InvalidValueError("Las duraciones del rasgueo deben ser positivas.")

    @classmethod
    def basic(cls, beats_per_bar: float) -> StrumPattern:
        whole = max(1, round(beats_per_bar))
        return cls(("abajo",) * whole, (beats_per_bar / whole,) * whole)

    @classmethod
    def from_text(cls, text: str, beats_per_bar: float) -> StrumPattern:
        """Lee la notación de casilleros: "D-DU-UDU" son ocho corcheas en un compás de 4/4."""
        slots = [char for char in text.upper() if not char.isspace()]
        if not slots or any(
            slot not in _STRUM_LETTERS and slot not in _STRUM_RESTS for slot in slots
        ):
            raise InvalidValueError(
                "Escribe el rasgueo con D (abajo), U (arriba), X (apagado) y -."
            )
        if slots[0] in _STRUM_RESTS:
            raise InvalidValueError("El rasgueo empieza con un golpe, no con un silencio.")
        size = beats_per_bar / len(slots)
        directions: list[str] = []
        beats: list[float] = []
        for slot in slots:
            if slot in _STRUM_RESTS:
                beats[-1] += size
                continue
            directions.append(_STRUM_LETTERS[slot])
            beats.append(size)
        return cls(tuple(directions), tuple(beats))

    def as_dict(self) -> dict[str, object]:
        return {"directions": list(self.directions), "beats": [_time(beat) for beat in self.beats]}

    @classmethod
    def from_dict(cls, raw: object) -> StrumPattern:
        if not isinstance(raw, dict):
            raise InvalidValueError("El rasgueo debe ser un objeto.")
        directions = raw.get("directions")
        beats = raw.get("beats")
        if not isinstance(directions, list) or not isinstance(beats, list):
            raise InvalidValueError("El rasgueo necesita direcciones y duraciones.")
        return cls(
            tuple(str(direction) for direction in directions),
            tuple(_number(beat, "La duración del golpe") for beat in beats),
        )


@dataclass(frozen=True, slots=True)
class GuideSection:
    name: str
    start: float
    beats: float
    strum: StrumPattern

    def __post_init__(self) -> None:
        if self.start < 0 or self.beats <= 0:
            raise InvalidValueError("La sección necesita un inicio y una duración positivos.")

    @property
    def end(self) -> float:
        return self.start + self.beats


@dataclass(frozen=True, slots=True)
class GuideChord:
    start: float
    beats: float
    chord: Chord

    def __post_init__(self) -> None:
        if self.start < 0 or self.beats <= 0:
            raise InvalidValueError("Cada acorde necesita un inicio y una duración positivos.")


@dataclass(frozen=True, slots=True)
class GuideNote:
    start: float
    beats: float
    midi: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.beats <= 0:
            raise InvalidValueError("Cada nota necesita un inicio y una duración positivos.")
        if not MIN_MIDI <= self.midi <= MAX_MIDI:
            raise InvalidValueError("La nota está fuera del registro de la guitarra.")


@dataclass(frozen=True, slots=True)
class SongGuide:
    title: str
    artist: str
    song_key: str | None
    bpm: Bpm
    beats_per_bar: float
    capo: int
    sections: tuple[GuideSection, ...]
    chords: tuple[GuideChord, ...]
    melody: tuple[GuideNote, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.artist.strip():
            raise InvalidValueError("La guía necesita título y artista.")
        if not 1 <= self.beats_per_bar <= 12:
            raise InvalidValueError("El compás debe tener entre 1 y 12 pulsos.")
        if not 0 <= self.capo <= 12:
            raise InvalidValueError("La cejilla va del traste 0 al 12.")
        if not self.chords:
            raise InvalidValueError("La guía no tiene acordes.")
        if not self.sections or len(self.sections) > MAX_SECTIONS:
            raise InvalidValueError(f"La guía necesita entre 1 y {MAX_SECTIONS} secciones.")
        if len(self.chords) > MAX_CHORDS or len(self.melody) > MAX_NOTES:
            raise InvalidValueError("La guía es demasiado larga.")
        ordered = sorted(self.sections, key=lambda section: section.start)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.start < previous.end - _EPSILON:
                raise InvalidValueError("Las secciones no pueden superponerse.")

    @property
    def total_beats(self) -> float:
        ends = [chord.start + chord.beats for chord in self.chords]
        ends.extend(section.end for section in self.sections)
        ends.extend(note.start + note.beats for note in self.melody)
        return max(ends)

    def chart(self) -> tuple[ChartChord, ...]:
        """La carta clásica (compás y pulso desde 1) que usan los intentos y el informe."""
        return tuple(
            ChartChord(
                bar=int(chord.start // self.beats_per_bar) + 1,
                beat=round(chord.start % self.beats_per_bar, 4) + 1,
                chord=chord.chord,
            )
            for chord in self.chords
        )

    def digest(self) -> str:
        raw = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def as_dict(self) -> dict[str, object]:
        return {
            "version": GUIDE_VERSION,
            "title": self.title,
            "artist": self.artist,
            "song_key": self.song_key,
            "bpm": self.bpm.value,
            "beats_per_bar": _time(self.beats_per_bar),
            "capo": self.capo,
            "sections": [
                {
                    "name": section.name,
                    "start": _time(section.start),
                    "beats": _time(section.beats),
                    "strum": section.strum.as_dict(),
                }
                for section in self.sections
            ],
            "chords": [
                {
                    "start": _time(chord.start),
                    "beats": _time(chord.beats),
                    "chord": chord.chord.symbol,
                }
                for chord in self.chords
            ],
            "melody": [
                {"start": _time(note.start), "beats": _time(note.beats), "midi": note.midi}
                for note in self.melody
            ],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> SongGuide:
        """Valida un documento que llega del cliente o de la base. Rechaza la letra."""
        if "lyrics" in raw:
            raise InvalidValueError("La guía no guarda la letra de la canción.")
        if raw.get("version", GUIDE_VERSION) != GUIDE_VERSION:
            raise InvalidValueError("Versión de guía no soportada.")
        beats_per_bar = _number(raw.get("beats_per_bar", 4), "El compás")
        key = _text(raw.get("song_key"), "La tonalidad", required=False)
        return cls(
            title=_text(raw.get("title"), "el título"),
            artist=_text(raw.get("artist"), "el artista"),
            song_key=key or None,
            bpm=Bpm(int(_number(raw.get("bpm"), "El tempo"))),
            beats_per_bar=beats_per_bar,
            capo=int(_number(raw.get("capo", 0), "La cejilla")),
            sections=tuple(
                GuideSection(
                    name=_text(item.get("name"), "el nombre de la sección"),
                    start=_number(item.get("start"), "El inicio de la sección"),
                    beats=_number(item.get("beats"), "La duración de la sección"),
                    strum=StrumPattern.from_dict(item.get("strum")),
                )
                for item in _items(raw.get("sections"), "Las secciones", MAX_SECTIONS)
            ),
            chords=tuple(
                GuideChord(
                    start=_number(item.get("start"), "El inicio del acorde"),
                    beats=_number(item.get("beats"), "La duración del acorde"),
                    chord=Chord.parse(str(item.get("chord", ""))),
                )
                for item in _items(raw.get("chords"), "Los acordes", MAX_CHORDS)
            ),
            melody=tuple(
                GuideNote(
                    start=_number(item.get("start"), "El inicio de la nota"),
                    beats=_number(item.get("beats"), "La duración de la nota"),
                    midi=int(_number(item.get("midi"), "La nota")),
                )
                for item in _items(raw.get("melody", []), "La melodía", MAX_NOTES)
            ),
        )


@dataclass(frozen=True, slots=True)
class GuideRecord:
    """La guía guardada, con su dueño y la canción que la representa en la práctica."""

    id: UUID
    owner_id: UUID
    song_id: int | None
    source_kind: str
    status: str
    guide: SongGuide
    content_hash: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.source_kind not in SOURCE_KINDS:
            raise InvalidValueError("Origen de guía desconocido.")
        if self.status not in STATUSES:
            raise InvalidValueError("Estado de guía desconocido.")
