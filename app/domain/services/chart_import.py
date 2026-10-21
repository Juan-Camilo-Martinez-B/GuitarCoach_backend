"""Lee ChordPro, texto con acordes y MusicXML. No descarga partituras ajenas."""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.domain.entities.study import StudyPlan, StudyStep
from app.domain.errors import InvalidValueError
from app.domain.value_objects.chord import Chord

_CHORD = re.compile(r"\[([A-G](?:#|b)?(?:maj7|m7|sus2|sus4|dim|aug|m|7)?)\]")
_DIRECTIVE = re.compile(r"\{([a-zA-Z]+):\s*([^}]*)\}")
_MELODY_LINE = re.compile(r"(?i)^melody:\s*(.+)$")
_FIELD = re.compile(r"(?i)^(title|artist|bpm|tempo|key):\s*(.+)$")
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
_MAX_BYTES = 200_000


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
    if len(raw) > _MAX_BYTES:
        raise InvalidValueError("El archivo supera 200 KB.")
    name = filename.lower()
    if name.endswith(".mxl"):
        raise InvalidValueError("Exporta MusicXML sin comprimir (.musicxml), no .mxl.")
    text = raw.decode("utf-8-sig", errors="replace")
    stem = Path(filename).stem or "Cancion"
    if name.endswith((".musicxml", ".xml")) or _looks_like_xml(text):
        return parse_musicxml(text, stem)
    if name.endswith(".txt"):
        return parse_plain(text, stem)
    return parse_chordpro(text, stem)


def parse_chordpro(text: str, fallback_title: str) -> ImportedChart:
    meta, chords, melody = _scan(text)
    title = meta.get("title") or meta.get("t") or fallback_title
    artist = meta.get("artist") or meta.get("subtitle") or meta.get("st") or "Archivo"
    return _chart(title, artist, meta, chords, melody)


def parse_plain(text: str, fallback_title: str) -> ImportedChart:
    return parse_chordpro(text, fallback_title)


def parse_musicxml(text: str, fallback_title: str) -> ImportedChart:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise InvalidValueError("El MusicXML no se pudo leer.") from error
    title = fallback_title
    for element in root.iter():
        if _local(element.tag) == "work-title" and element.text:
            title = element.text.strip()
    chords = _xml_chords(root)
    melody = _xml_melody(root)
    if not chords and not melody:
        raise InvalidValueError("El MusicXML no trae acordes ni notas.")
    if not chords:
        chords = tuple((bar, beat, note) for bar, beat, note in melody)
    meta = {"title": title, "artist": "MusicXML", "tempo": "80"}
    return _chart(title, "MusicXML", meta, chords, melody)


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


def _chart(
    title: str,
    artist: str,
    meta: dict[str, str],
    chords: tuple[tuple[int, float, str], ...],
    melody: tuple[tuple[int, float, str], ...],
) -> ImportedChart:
    if not chords:
        raise InvalidValueError("El archivo no tiene acordes ni notas reconocibles.")
    bpm_text = meta.get("tempo") or meta.get("bpm") or "80"
    try:
        bpm = int(float(bpm_text))
    except ValueError as error:
        raise InvalidValueError("El tempo del archivo no es un número.") from error
    song_key = meta.get("key") or meta.get("k")
    for _, _, symbol in chords:
        Chord.parse(symbol)
    return ImportedChart(title.strip(), artist.strip() or "Archivo", song_key, bpm, chords, melody)


def _scan(
    text: str,
) -> tuple[dict[str, str], tuple[tuple[int, float, str], ...], tuple[tuple[int, float, str], ...]]:
    meta: dict[str, str] = {}
    chord_symbols: list[str] = []
    melody_symbols: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        field = _FIELD.match(line)
        if field:
            meta[field.group(1).lower()] = field.group(2).strip()
            continue
        melody_match = _MELODY_LINE.match(line)
        if melody_match:
            melody_symbols.extend(_notes(melody_match.group(1)))
            continue
        for key, value in _DIRECTIVE.findall(line):
            meta[key.lower()] = value.strip()
        chord_symbols.extend(match.group(1) for match in _CHORD.finditer(line))
        if not _CHORD.search(line) and not line.startswith("{"):
            chord_symbols.extend(_notes(line))
    return meta, _place(chord_symbols), _place(melody_symbols)


def _notes(text: str) -> list[str]:
    found: list[str] = []
    for token in text.replace("|", " ").split():
        try:
            found.append(Chord.parse(token).symbol)
        except InvalidValueError:
            continue
    return found


def _place(symbols: list[str]) -> tuple[tuple[int, float, str], ...]:
    placed: list[tuple[int, float, str]] = []
    for index, symbol in enumerate(symbols):
        placed.append((index // 4 + 1, float(index % 4 + 1), symbol))
    return tuple(placed)


def _xml_chords(root: ET.Element) -> tuple[tuple[int, float, str], ...]:
    symbols: list[str] = []
    for element in root.iter():
        if _local(element.tag) != "harmony":
            continue
        step = _child_text(element, "root-step")
        if not step:
            continue
        alter = _child_text(element, "root-alter")
        kind = _child_text(element, "kind") or ""
        accidental = "#" if alter == "1" else "b" if alter == "-1" else ""
        quality = "m" if "minor" in kind else ""
        symbols.append(f"{step}{accidental}{quality}")
    return _place(symbols)


def _xml_melody(root: ET.Element) -> tuple[tuple[int, float, str], ...]:
    symbols: list[str] = []
    for element in root.iter():
        if _local(element.tag) != "note":
            continue
        if any(_local(child.tag) in {"rest", "chord"} for child in element):
            continue
        step = None
        alter = None
        for child in element.iter():
            if _local(child.tag) == "step":
                step = child.text
            elif _local(child.tag) == "alter":
                alter = child.text
        if not step:
            continue
        accidental = "#" if alter == "1" else "b" if alter == "-1" else ""
        symbols.append(f"{step}{accidental}")
    return _place(symbols)


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _looks_like_xml(text: str) -> bool:
    sample = text.lstrip()[:400]
    return sample.startswith("<?xml") or "<score-partwise" in sample


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
