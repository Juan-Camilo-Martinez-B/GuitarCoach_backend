"""Convierte texto de acordes (ChordPro o copiado de un cancionero) y MusicXML en una guía.

La letra se lee solo para ubicar los acordes y se descarta: nunca llega a la guía.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from app.domain.entities.guide import (
    MAX_CHORDS,
    MAX_NOTES,
    MAX_SECTIONS,
    GuideChord,
    GuideNote,
    GuideSection,
    SongGuide,
    StrumEvent,
    StrumPattern,
    events_from_chords,
    expand_pattern,
    expand_slots,
)
from app.domain.errors import InvalidValueError
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord

MAX_BYTES = 200_000
DEFAULT_BPM = 80
DEFAULT_SECTION = "Canción"

_DIRECTIVE = re.compile(r"^\{\s*([a-zA-Z_]+)\s*(?::\s*(.*?))?\s*\}$")
_INLINE_CHORD = re.compile(r"\[([^\]\s]{1,12})\]")
_FIELD = re.compile(
    r"(?i)^(title|titulo|título|artist|artista|bpm|tempo|key|tono|tonalidad|capo|cejilla|time|compas|compás|strum|rasgueo):\s*(.+)$"
)
_MELODY_LINE = re.compile(r"(?i)^(melody|melodia|melodía):\s*(.+)$")
_REPEAT = re.compile(r"(?i)^\(?(?:x\s*(\d{1,2})|(\d{1,2})\s*x)\)?$")
_CAPO_LINE = re.compile(r"(?i)^(?:capo|cejilla|capotraste)\D{0,12}(\d{1,2})\b")
_NOTE = re.compile(
    r"^(?P<step>[A-Ga-g])(?P<accidental>#|b)?(?P<octave>-?\d)?(?::(?P<beats>\d+(?:\.\d+)?))?$"
)
_SECTION_WORDS = (
    "intro",
    "introduccion",
    "introducción",
    "verso",
    "estrofa",
    "coro",
    "estribillo",
    "precoro",
    "pre-coro",
    "pre coro",
    "puente",
    "interludio",
    "solo",
    "final",
    "outro",
    "verse",
    "chorus",
    "pre-chorus",
    "prechorus",
    "bridge",
    "interlude",
    "ending",
)
_SECTION_LINE = re.compile(
    r"(?i)^\[?\s*(?P<name>(?:"
    + "|".join(re.escape(word) for word in _SECTION_WORDS)
    + r")\b[^\]:]{0,20})\s*\]?\s*:?\s*(?P<rest>.*)$"
)
_DIRECTIVE_SECTIONS = {
    "start_of_chorus": "Coro",
    "soc": "Coro",
    "start_of_verse": "Verso",
    "sov": "Verso",
    "start_of_bridge": "Puente",
    "sob": "Puente",
}
_IGNORED_BLOCKS = {"start_of_tab": "end_of_tab", "sot": "eot", "start_of_grid": "end_of_grid"}
_PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# Etiquetas que deja el texto copiado de algunos cancioneros.
_MARKUP = re.compile(r"\[/?(?:ch|tab)\]", re.IGNORECASE)
_PLACEHOLDERS = {".", "/", "-"}
_REPEAT_BAR = "%"


@dataclass(slots=True)
class _Meta:
    title: str | None = None
    artist: str | None = None
    song_key: str | None = None
    bpm: int | None = None
    beats_per_bar: float = 4
    capo: int = 0
    strum: str | None = None


@dataclass(slots=True)
class _Section:
    name: str
    start: float
    strum: str | None


@dataclass(slots=True)
class _Timeline:
    """Acumula compases y secciones mientras se recorre el texto."""

    beats_per_bar: float
    cursor: float = 0
    melody_cursor: float = 0
    chords: list[GuideChord] = field(default_factory=list)
    melody: list[GuideNote] = field(default_factory=list)
    sections: list[_Section] = field(default_factory=list)
    last_bar: list[tuple[float, Chord]] = field(default_factory=list)

    def open_section(self, name: str, strum: str | None = None) -> None:
        if self.sections and self.sections[-1].start == self.cursor:
            self.sections[-1].name = name
            self.sections[-1].strum = strum or self.sections[-1].strum
            return
        if len(self.sections) >= MAX_SECTIONS:
            raise InvalidValueError(f"La canción supera {MAX_SECTIONS} secciones.")
        self.sections.append(_Section(name, self.cursor, strum))

    def set_strum(self, strum: str) -> None:
        if not self.sections or self.sections[-1].start != self.cursor:
            self.open_section(self.sections[-1].name if self.sections else DEFAULT_SECTION, strum)
        else:
            self.sections[-1].strum = strum

    def bar(self, slots: list[Chord | None]) -> None:
        """Un compás: cada casillero vale lo mismo y None prolonga el acorde anterior."""
        if not slots:
            return
        if len(self.chords) >= MAX_CHORDS:
            raise InvalidValueError("La canción tiene demasiados acordes.")
        if not self.sections:
            self.open_section(DEFAULT_SECTION)
        size = self.beats_per_bar / len(slots)
        placed: list[tuple[float, Chord]] = []
        for index, chord in enumerate(slots):
            offset = index * size
            if chord is not None:
                placed.append((offset, chord))
            elif not placed and self.chords:
                # El compás empieza prolongando el último acorde de la línea anterior.
                placed.append((offset, self.chords[-1].chord))
        for index, (offset, chord) in enumerate(placed):
            following = placed[index + 1][0] if index + 1 < len(placed) else self.beats_per_bar
            self.chords.append(GuideChord(self.cursor + offset, following - offset, chord))
        self.last_bar = placed
        self.cursor += self.beats_per_bar

    def repeat_bar(self) -> None:
        if not self.last_bar:
            raise InvalidValueError("% repite un compás, pero todavía no hay ninguno.")
        offsets = {offset: chord for offset, chord in self.last_bar}
        slots: list[Chord | None] = [offsets.get(0.0)]
        if len(offsets) > 1:
            step = min(
                later - earlier
                for earlier, later in zip(sorted(offsets), sorted(offsets)[1:], strict=False)
            )
            count = round(self.beats_per_bar / step)
            slots = [offsets.get(round(index * step, 6)) for index in range(count)]
        self.bar(slots)

    def note(self, midi: int, beats: float) -> None:
        if len(self.melody) >= MAX_NOTES:
            raise InvalidValueError("La melodía tiene demasiadas notas.")
        self.melody.append(GuideNote(self.melody_cursor, beats, midi))
        self.melody_cursor += beats

    def build(self, meta: _Meta, fallback_title: str) -> SongGuide:
        if not self.chords:
            raise InvalidValueError("El texto no tiene acordes reconocibles.")
        total = max(self.cursor, self.melody_cursor)
        sections: list[GuideSection] = []
        events: list[StrumEvent] = []
        for index, section in enumerate(self.sections):
            end = self.sections[index + 1].start if index + 1 < len(self.sections) else total
            if end - section.start <= 0:
                continue
            strum_text = section.strum or meta.strum
            if strum_text:
                pattern = StrumPattern.from_text(strum_text, self.beats_per_bar)
                events.extend(
                    expand_slots(
                        strum_text,
                        section.start,
                        end - section.start,
                        self.beats_per_bar,
                        "escrito",
                    )
                )
            else:
                pattern = StrumPattern.lesson(self.beats_per_bar)
                events.extend(
                    expand_pattern(
                        section.start,
                        end - section.start,
                        self.beats_per_bar,
                        pattern,
                        "leccion",
                    )
                )
            sections.append(GuideSection(section.name, section.start, end - section.start, pattern))
        # Sin notas escritas la guía queda sin melodía: inventarla enseñaría otra canción.
        melody = tuple(self.melody)
        return SongGuide(
            title=(meta.title or fallback_title).strip() or "Canción",
            artist=(meta.artist or "Sin artista").strip() or "Sin artista",
            song_key=meta.song_key,
            bpm=Bpm(meta.bpm or DEFAULT_BPM),
            beats_per_bar=self.beats_per_bar,
            capo=meta.capo,
            sections=tuple(sections),
            chords=tuple(self.chords),
            melody=melody,
            events=tuple(events),
        )


def guide_from_file(filename: str, raw: bytes) -> tuple[SongGuide, str]:
    """Lee un archivo subido. Devuelve la guía y su tipo de origen."""
    if len(raw) > MAX_BYTES:
        raise InvalidValueError("El archivo supera 200 KB.")
    name = filename.lower()
    if name.endswith(".mxl"):
        raise InvalidValueError("Exporta MusicXML sin comprimir (.musicxml), no .mxl.")
    text = raw.decode("utf-8-sig", errors="replace")
    stem = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0] or "Canción"
    if name.endswith((".musicxml", ".xml")) or _looks_like_xml(text):
        return guide_from_musicxml(text, stem), "musicxml"
    return guide_from_text(text, stem), "chordpro"


def guide_from_text(
    text: str,
    fallback_title: str,
    *,
    title: str | None = None,
    artist: str | None = None,
    bpm: int | None = None,
    beats_per_bar: float | None = None,
    capo: int | None = None,
    strum: str | None = None,
) -> SongGuide:
    """ChordPro, texto con acordes entre corchetes o acordes copiados sobre la letra."""
    if len(text.encode()) > MAX_BYTES:
        raise InvalidValueError("El texto supera 200 KB.")
    meta = _Meta()
    lines = [_MARKUP.sub("", line).rstrip() for line in text.splitlines()]
    _read_meta(lines, meta)
    meta.title = title or meta.title
    meta.artist = artist or meta.artist
    meta.bpm = bpm or meta.bpm
    meta.beats_per_bar = beats_per_bar or meta.beats_per_bar
    meta.capo = capo if capo is not None else meta.capo
    meta.strum = strum or meta.strum
    timeline = _Timeline(meta.beats_per_bar)
    _read_body(lines, timeline)
    return timeline.build(meta, fallback_title)


def _read_meta(lines: list[str], meta: _Meta) -> None:
    for raw in lines:
        line = raw.strip()
        directive = _DIRECTIVE.match(line)
        key, value = (
            (directive.group(1).lower(), (directive.group(2) or "").strip())
            if directive
            else ("", "")
        )
        if not directive:
            field_match = _FIELD.match(line)
            if field_match:
                key, value = field_match.group(1).lower(), field_match.group(2).strip()
            else:
                capo_match = _CAPO_LINE.match(line)
                if capo_match:
                    meta.capo = _capo(capo_match.group(1))
                continue
        if key in {"title", "t", "titulo", "título"}:
            meta.title = value
        elif key in {"artist", "artista", "subtitle", "st"}:
            meta.artist = meta.artist or value
        elif key in {"key", "k", "tono", "tonalidad"}:
            chord = Chord.read(value)
            meta.song_key = chord.symbol if chord else value or None
        elif key in {"tempo", "bpm"}:
            meta.bpm = _bpm(value)
        elif key in {"time", "compas", "compás"}:
            meta.beats_per_bar = parse_time_signature(value)
        elif key in {"capo", "cejilla"}:
            meta.capo = _capo(value)
        elif key in {"strum", "rasgueo"} and meta.strum is None:
            meta.strum = value
        elif key in {"comment", "c", "ci", "comment_italic"} and meta.bpm is None:
            hinted = _tempo_hint(value)
            if hinted is not None:
                meta.bpm = hinted


def _read_body(lines: list[str], timeline: _Timeline) -> None:
    skipping: str | None = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        directive = _DIRECTIVE.match(line)
        if directive:
            key = directive.group(1).lower()
            value = (directive.group(2) or "").strip()
            if skipping:
                skipping = None if key == skipping else skipping
            elif key in _IGNORED_BLOCKS:
                skipping = _IGNORED_BLOCKS[key]
            elif key in _DIRECTIVE_SECTIONS:
                timeline.open_section(value or _DIRECTIVE_SECTIONS[key])
            elif key in {"comment", "c", "ci", "comment_italic"} and value:
                section = _SECTION_LINE.match(value)
                if section:
                    timeline.open_section(_section_name(section.group("name")))
            elif key in {"strum", "rasgueo"} and value and timeline.sections:
                timeline.set_strum(value)
            continue
        if skipping or _FIELD.match(line) or _CAPO_LINE.match(line):
            continue
        melody = _MELODY_LINE.match(line)
        if melody:
            for midi, beats in _notes(melody.group(2)):
                timeline.note(midi, beats)
            continue
        section = _SECTION_LINE.match(line)
        if section and not _is_chord_line(line):
            rest = section.group("rest").strip()
            timeline.open_section(_section_name(section.group("name")))
            if rest and _is_chord_line(rest):
                _read_chord_line(rest, timeline)
            continue
        if _is_chord_line(line):
            _read_chord_line(line, timeline)
            continue
        inline = [Chord.read(match) for match in _INLINE_CHORD.findall(line)]
        # Acordes dentro de la letra: cada uno ocupa un compás. La letra se descarta.
        for chord in inline:
            if chord is not None:
                timeline.bar([chord])


def _tokens(line: str) -> list[str]:
    spaced = line.replace("|", " | ").replace("[", " ").replace("]", " ")
    return spaced.split()


def _is_chord_line(line: str) -> bool:
    tokens = [token for token in _tokens(line) if token != "|"]
    if not tokens:
        return "|" in line
    chords = 0
    for index, token in enumerate(tokens):
        if Chord.read(token) is not None:
            chords += 1
        elif token in _PLACEHOLDERS or token == _REPEAT_BAR:
            continue
        elif index == len(tokens) - 1 and _REPEAT.match(token):
            continue
        else:
            return False
    return chords > 0 or _REPEAT_BAR in tokens


def _read_chord_line(line: str, timeline: _Timeline) -> None:
    tokens = _tokens(line)
    times = 1
    if tokens and _REPEAT.match(tokens[-1]):
        found = _REPEAT.match(tokens[-1])
        times = max(1, min(16, int((found.group(1) or found.group(2)) if found else 1)))
        tokens = tokens[:-1]
    bars = _split_bars(tokens)
    for _ in range(times):
        for bar in bars:
            if bar is None:
                timeline.repeat_bar()
            else:
                timeline.bar(bar)


# Un compás son sus casilleros; None en lugar del compás significa "repite el anterior" (%).
_Bar = list[Chord | None] | None


def _split_bars(tokens: list[str]) -> list[_Bar]:
    """Con barras, cada tramo entre | es un compás. Sin barras, cada acorde es un compás."""
    if "|" not in tokens:
        bars: list[_Bar] = []
        for token in tokens:
            chord = Chord.read(token)
            if chord is not None:
                bars.append([chord])
            elif token == _REPEAT_BAR:
                bars.append(None)
        return bars
    bars = []
    current: list[str] = []
    for token in [*tokens, "|"]:
        if token != "|":
            current.append(token)
            continue
        if current == [_REPEAT_BAR]:
            bars.append(None)
        elif current:
            bars.append([None if item in _PLACEHOLDERS else Chord.read(item) for item in current])
        current = []
    return bars


def _notes(text: str) -> list[tuple[int, float]]:
    found: list[tuple[int, float]] = []
    for token in text.replace("|", " ").split():
        match = _NOTE.match(token)
        if match is None:
            continue
        pitch = _PITCH[match.group("step").upper()]
        accidental = {"#": 1, "b": -1}.get(match.group("accidental") or "", 0)
        octave = int(match.group("octave")) if match.group("octave") else 4
        beats = float(match.group("beats")) if match.group("beats") else 1.0
        found.append((12 * (octave + 1) + pitch + accidental, beats))
    return found


def _section_name(raw: str) -> str:
    name = " ".join(raw.split()).strip(" :[]")
    return name[:1].upper() + name[1:] if name else DEFAULT_SECTION


def _tempo_hint(text: str) -> int | None:
    match = re.search(r"(?i)\b(?:tempo|bpm)\b\D{0,6}(\d{2,3})\b|\b(\d{2,3})\s*bpm\b", text)
    if match is None:
        return None
    value = int(match.group(1) or match.group(2))
    if 40 <= value <= 240:
        return value
    return None


def _bpm(value: str) -> int:
    digits = re.search(r"\d+(?:\.\d+)?", value)
    if digits is None:
        raise InvalidValueError("El tempo del archivo no es un número.")
    return int(float(digits.group(0)))


def _capo(value: str) -> int:
    digits = re.search(r"\d+", value)
    return int(digits.group(0)) if digits else 0


def parse_time_signature(value: str) -> float:
    match = re.match(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$", value)
    if match is None:
        raise InvalidValueError("El compás se escribe como 4/4, 3/4 o 6/8.")
    beats, unit = int(match.group(1)), int(match.group(2))
    if unit not in {2, 4, 8, 16}:
        raise InvalidValueError("La figura del compás debe ser 2, 4, 8 o 16.")
    return beats * 4 / unit


# --- MusicXML -------------------------------------------------------------------------

_KIND_QUALITY = {
    "major": "",
    "minor": "m",
    "dominant": "7",
    "major-seventh": "maj7",
    "minor-seventh": "m7",
    "diminished": "dim",
    "diminished-seventh": "dim7",
    "half-diminished": "m7b5",
    "augmented": "aug",
    "suspended-second": "sus2",
    "suspended-fourth": "sus4",
    "major-sixth": "6",
    "minor-sixth": "m6",
    "dominant-ninth": "9",
    "major-ninth": "maj9",
    "minor-ninth": "m9",
}


def guide_from_musicxml(text: str, fallback_title: str) -> SongGuide:
    # Sin entidades: evita documentos que se expanden hasta agotar la memoria.
    if "<!ENTITY" in text:
        raise InvalidValueError("El MusicXML no puede declarar entidades.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise InvalidValueError("El MusicXML no se pudo leer.") from error
    title = _first_text(root, "work-title") or _first_text(root, "movement-title") or fallback_title
    artist = _first_text(root, "creator") or "MusicXML"
    part = _guitar_part(root)

    divisions = 1.0
    beats_per_bar = 4.0
    bpm: int | None = None
    measure_start = 0.0
    harmonies: list[tuple[float, Chord]] = []
    notes: list[GuideNote] = []
    marks: list[tuple[float, str]] = []
    pitch = _SoundingPitch()

    measures = [element for element in part if _local(element.tag) == "measure"]
    for measure in (measures[index] for index in _playback_order(measures)):
        position = 0.0
        longest = 0.0
        for element in measure:
            tag = _local(element.tag)
            if tag == "attributes":
                divisions = float(_child_text(element, "divisions") or divisions)
                beats = _child_text(element, "beats")
                unit = _child_text(element, "beat-type")
                if beats and unit:
                    beats_per_bar = parse_time_signature(f"{beats}/{unit}")
                pitch.read_attributes(element)
            elif tag == "direction":
                bpm = bpm or _tempo(element)
                rehearsal = _child_text(element, "rehearsal")
                if rehearsal:
                    marks.append((measure_start + position, rehearsal))
            elif tag == "harmony":
                chord = _harmony(element)
                if chord is not None:
                    harmonies.append((measure_start + position, chord))
            elif tag == "note":
                length = float(_child_text(element, "duration") or 0) / divisions
                is_chord_tone = _has_child(element, "chord")
                if _has_child(element, "grace"):
                    continue
                if not is_chord_tone:
                    midi = pitch.sounding(element)
                    voice = _child_text(element, "voice") or "1"
                    if midi is not None and voice == "1" and length > 0:
                        _add_note(notes, measure_start + position, length, midi, _tie_stop(element))
                    position += length
            elif tag == "backup":
                position -= float(_child_text(element, "duration") or 0) / divisions
            elif tag == "forward":
                position += float(_child_text(element, "duration") or 0) / divisions
            longest = max(longest, position)
        measure_start += max(longest, beats_per_bar)

    total = measure_start
    if not harmonies and not notes:
        raise InvalidValueError("El MusicXML no trae acordes ni notas.")
    if len(harmonies) > MAX_CHORDS or len(notes) > MAX_NOTES:
        raise InvalidValueError("El MusicXML es demasiado largo para una guía.")
    if not harmonies:
        # Sin cifrado armónico: la fundamental de cada compás guía la práctica.
        harmonies = _bar_roots(notes, beats_per_bar)
    chords = tuple(
        GuideChord(
            start, (harmonies[index + 1][0] if index + 1 < len(harmonies) else total) - start, chord
        )
        for index, (start, chord) in enumerate(harmonies)
        if (harmonies[index + 1][0] if index + 1 < len(harmonies) else total) > start
    )
    return SongGuide(
        title=title.strip() or "Canción",
        artist=artist.strip() or "MusicXML",
        song_key=None,
        bpm=Bpm(bpm or DEFAULT_BPM),
        beats_per_bar=beats_per_bar,
        capo=0,
        sections=_xml_sections(marks, total, beats_per_bar),
        chords=chords,
        melody=tuple(notes),
        events=events_from_chords(chords, "escrito"),
    )


def _add_note(notes: list[GuideNote], start: float, length: float, midi: int, tied: bool) -> None:
    previous = notes[-1] if notes else None
    if (
        tied
        and previous
        and previous.midi == midi
        and abs(previous.start + previous.beats - start) < 1e-6
    ):
        notes[-1] = GuideNote(previous.start, previous.beats + length, midi)
        return
    notes.append(GuideNote(start, length, midi))


def _bar_roots(notes: list[GuideNote], beats_per_bar: float) -> list[tuple[float, Chord]]:
    roots: list[tuple[float, Chord]] = []
    seen: set[int] = set()
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    for note in notes:
        bar = int(note.start // beats_per_bar)
        if bar in seen:
            continue
        seen.add(bar)
        roots.append((bar * beats_per_bar, Chord.parse(names[note.midi % 12])))
    return roots


def _xml_sections(
    marks: list[tuple[float, str]], total: float, beats_per_bar: float
) -> tuple[GuideSection, ...]:
    starts = [(0.0, DEFAULT_SECTION)] + [mark for mark in marks if mark[0] > 0]
    sections = []
    for index, (start, name) in enumerate(starts[:MAX_SECTIONS]):
        end = starts[index + 1][0] if index + 1 < len(starts) else total
        if end > start:
            titled = _section_name(name)
            sections.append(
                GuideSection(titled, start, end - start, StrumPattern.basic(beats_per_bar))
            )
    return tuple(sections)


def _harmony(element: ET.Element) -> Chord | None:
    step = _child_text(element, "root-step")
    if not step:
        return None
    alter = _child_text(element, "root-alter")
    accidental = "#" if alter == "1" else "b" if alter == "-1" else ""
    kind = _child_text(element, "kind") or "major"
    return Chord.read(f"{step}{accidental}{_KIND_QUALITY.get(kind, '')}")


def _midi(element: ET.Element) -> int | None:
    if _has_child(element, "rest"):
        return None
    step = _child_text(element, "step")
    octave = _child_text(element, "octave")
    if not step or octave is None:
        return None
    alter = round(float(_child_text(element, "alter") or 0))
    return 12 * (int(octave) + 1) + _PITCH[step.upper()] + alter


_GUITAR_WORDS = ("guit", "guitar", "guitarra")
# Tope de compases al desplegar repeticiones: un archivo mal formado no crece sin fin.
MAX_PLAYED_MEASURES = 2000


def _guitar_part(root: ET.Element) -> ET.Element:
    """La parte de guitarra: la que trae tablatura o se llama guitarra. Si no hay, la primera."""
    parts = [element for element in root if _local(element.tag) == "part"]
    if not parts:
        raise InvalidValueError("El MusicXML no trae partes.")
    names: dict[str, str] = {}
    for element in root.iter():
        if _local(element.tag) == "score-part":
            label = " ".join(
                (child.text or "")
                for child in element.iter()
                if _local(child.tag) in {"part-name", "instrument-name"}
            )
            names[element.get("id", "")] = label.lower()

    def has_tab(part: ET.Element) -> bool:
        return any(_local(child.tag) == "staff-tuning" for child in part.iter())

    def named_guitar(part: ET.Element) -> bool:
        return any(word in names.get(part.get("id", ""), "") for word in _GUITAR_WORDS)

    # Un Element sin hijos es falso al evaluarlo: se compara con None, no con "or".
    for matches in (has_tab, named_guitar):
        found = next((part for part in parts if matches(part)), None)
        if found is not None:
            return found
    return parts[0]


@dataclass(slots=True)
class _SoundingPitch:
    """La altura que suena. La tablatura manda; si no hay, lo escrito más la transposición.

    La guitarra se escribe una octava por encima de como suena: los archivos lo declaran
    con <transpose><octave-change>-1</octave-change></transpose>.
    """

    shift: int = 0
    capo: int = 0
    # Cuerda (1 es la más aguda, como en <string>) -> MIDI al aire.
    tuning: dict[int, int] = field(default_factory=dict)

    def read_attributes(self, attributes: ET.Element) -> None:
        for child in attributes.iter():
            tag = _local(child.tag)
            if tag == "transpose":
                chromatic = round(float(_child_text(child, "chromatic") or 0))
                octaves = int(_child_text(child, "octave-change") or 0)
                self.shift = chromatic + 12 * octaves
            elif tag == "staff-details":
                self._read_tab(child)

    def _read_tab(self, details: ET.Element) -> None:
        tunings = [child for child in details if _local(child.tag) == "staff-tuning"]
        lines = _child_text(details, "staff-lines")
        count = int(lines) if lines and lines.isdigit() else len(tunings)
        tuning: dict[int, int] = {}
        for item in tunings:
            line = int(item.get("line", "0"))
            step = _child_text(item, "tuning-step")
            octave = _child_text(item, "tuning-octave")
            if not step or octave is None or not 1 <= line <= count:
                continue
            alter = round(float(_child_text(item, "tuning-alter") or 0))
            # La línea 1 de la tablatura es la cuerda más grave.
            tuning[count + 1 - line] = 12 * (int(octave) + 1) + _PITCH[step.upper()] + alter
        if tuning:
            self.tuning = tuning
        capo = _child_text(details, "capo")
        if capo and capo.isdigit():
            self.capo = int(capo)

    def sounding(self, note: ET.Element) -> int | None:
        if _has_child(note, "rest"):
            return None
        string = _child_text(note, "string")
        fret = _child_text(note, "fret")
        if string and fret and string.isdigit() and fret.isdigit():
            open_string = self.tuning.get(int(string))
            if open_string is not None:
                return open_string + int(fret) + self.capo
        written = _midi(note)
        return None if written is None else written + self.shift


def _barline_marks(measure: ET.Element) -> tuple[int | None, bool, set[int] | None, bool]:
    """Repetición atrás (veces), repetición adelante, casilla que abre y casilla que cierra."""
    backward: int | None = None
    forward = False
    opens: set[int] | None = None
    closes = False
    for barline in (child for child in measure if _local(child.tag) == "barline"):
        for child in barline:
            tag = _local(child.tag)
            if tag == "repeat" and child.get("direction") == "backward":
                times = child.get("times", "2")
                backward = int(times) if times.isdigit() else 2
            elif tag == "repeat" and child.get("direction") == "forward":
                forward = True
            elif tag == "ending" and child.get("type") == "start":
                opens = {int(number) for number in re.findall(r"\d+", child.get("number", ""))}
            elif tag == "ending" and child.get("type") in {"stop", "discontinue"}:
                closes = True
    return backward, forward, opens, closes


def _playback_order(measures: list[ET.Element]) -> list[int]:
    """Índices de compás en el orden en que suenan, con repeticiones y casillas 1.ª y 2.ª."""
    marks = [_barline_marks(measure) for measure in measures]
    endings: list[set[int] | None] = []
    current: set[int] | None = None
    for _, _, opens, closes in marks:
        if opens is not None:
            current = opens
        endings.append(current)
        if closes:
            current = None

    order: list[int] = []
    index = 0
    start = 0
    passes = 1
    jumped_from = -1
    while index < len(measures) and len(order) < MAX_PLAYED_MEASURES:
        backward, forward, _, _ = marks[index]
        allowed = endings[index]
        if passes > 1 and index > jumped_from and allowed is None:
            # Ya se salió de las casillas: lo que sigue es una sola pasada.
            passes = 1
            start = index
        if forward and passes == 1:
            start = index
        if allowed and passes not in allowed:
            index += 1
            continue
        order.append(index)
        if backward is not None and passes < backward:
            passes += 1
            jumped_from = index
            index = start
            continue
        if backward is not None and allowed is None:
            passes = 1
            start = index + 1
        index += 1
    return order


def _tie_stop(element: ET.Element) -> bool:
    return any(
        _local(child.tag) == "tie" and child.get("type") == "stop" for child in element.iter()
    )


def _tempo(element: ET.Element) -> int | None:
    for child in element.iter():
        if _local(child.tag) == "sound" and child.get("tempo"):
            return round(float(child.get("tempo", "0")))
    per_minute = _child_text(element, "per-minute")
    return (
        round(float(per_minute)) if per_minute and per_minute.replace(".", "").isdigit() else None
    )


def _first_text(root: ET.Element, name: str) -> str | None:
    for element in root.iter():
        if _local(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return None


def _has_child(element: ET.Element, name: str) -> bool:
    return any(_local(child.tag) == name for child in element)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _looks_like_xml(text: str) -> bool:
    sample = text.lstrip()[:400]
    return sample.startswith("<?xml") or "<score-partwise" in sample
