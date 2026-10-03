"""Canción normalizada. Los acordes ya no dependen del HTML de origen."""

from dataclasses import dataclass

from app.domain.errors import InvalidValueError
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord


@dataclass(frozen=True, slots=True)
class ChartChord:
    bar: int
    beat: float
    chord: Chord

    def __post_init__(self) -> None:
        if self.bar < 1 or self.beat <= 0:
            raise InvalidValueError("El compás y el pulso deben ser positivos.")


@dataclass(frozen=True, slots=True)
class Song:
    title: str
    artist: str
    song_key: str | None
    bpm: Bpm
    chords: tuple[ChartChord, ...]
    source_url: str | None
    source_name: str | None
    content_hash: str
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.artist.strip():
            raise InvalidValueError("La canción necesita título y artista.")
        if not self.chords:
            raise InvalidValueError("La canción no tiene acordes.")
        if not self.content_hash.strip():
            raise InvalidValueError("Falta el hash de contenido para la caché.")
