"""Pulso, acordes y, si se pide, melodía de un audio del usuario.

El archivo vive solo en un directorio temporal mientras se analiza y se borra siempre.
Nada del audio se guarda en la base: solo la guía que resulta.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.errors import ExternalServiceError, InvalidValueError

MAX_BYTES = 10 * 1024 * 1024
MAX_SECONDS = 360
SAMPLE_RATE = 22050
HOP = 512
MIN_BEATS = 8
# Probabilidad de quedarse en el mismo acorde de un pulso al siguiente: suaviza el parpadeo.
SELF_TRANSITION = 0.9
# Por debajo de esta energía relativa el pulso cuenta como silencio, sin acorde.
SILENCE_RATIO = 0.08
SHARPNESS = 18.0
MIN_NOTE_SECONDS = 0.08
_ROOTS = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


@dataclass(frozen=True, slots=True)
class AnalyzedChord:
    start: float
    beats: float
    symbol: str


@dataclass(frozen=True, slots=True)
class AnalyzedNote:
    start: float
    beats: float
    midi: int


@dataclass(frozen=True, slots=True)
class AudioAnalysis:
    bpm: int
    chords: tuple[AnalyzedChord, ...]
    melody: tuple[AnalyzedNote, ...]


def sniff_audio(raw: bytes) -> str | None:
    """Reconoce el formato por su contenido, no por la extensión que manda el cliente."""
    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return ".wav"
    if raw[:4] == b"OggS":
        return ".ogg"
    if raw[:4] == b"fLaC":
        return ".flac"
    if raw[:3] == b"ID3" or (len(raw) > 1 and raw[0] == 0xFF and raw[1] & 0xE0 == 0xE0):
        return ".mp3"
    return None


def analyze_bytes(raw: bytes, *, melody: bool = False) -> AudioAnalysis:
    if len(raw) > MAX_BYTES:
        raise InvalidValueError("El audio supera 10 MB.")
    suffix = sniff_audio(raw)
    if suffix is None:
        raise InvalidValueError("Sube un audio WAV, MP3, OGG o FLAC.")
    with tempfile.TemporaryDirectory(prefix="guitarcoach-audio-") as folder:
        path = Path(folder) / f"subido{suffix}"
        path.write_bytes(raw)
        return analyze_file(path, melody=melody)


def _librosa() -> Any:
    try:
        import librosa
    except ImportError as error:
        raise ExternalServiceError(
            "El análisis de audio no está instalado en el servidor (pip install -e .[analysis])."
        ) from error
    return librosa


def _templates(np: Any) -> tuple[Any, list[str]]:
    rows: list[Any] = []
    names: list[str] = []
    for index, root in enumerate(_ROOTS):
        for quality, third in (("", 4), ("m", 3)):
            row = np.zeros(12)
            row[[index, (index + third) % 12, (index + 7) % 12]] = [1.4, 1.0, 1.0]
            rows.append(row / np.linalg.norm(row))
            names.append(f"{root}{quality}")
    return np.array(rows), names


def analyze_file(path: Path, *, melody: bool = False) -> AudioAnalysis:
    librosa = _librosa()
    import numpy as np

    try:
        duration = float(librosa.get_duration(path=str(path)))
    except Exception as error:
        raise InvalidValueError("El audio no se pudo leer.") from error
    if duration > MAX_SECONDS:
        raise InvalidValueError("El audio dura más de 6 minutos.")
    signal, rate = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    if signal.size == 0 or float(np.max(np.abs(signal))) < 1e-4:
        raise InvalidValueError("El audio está en silencio.")

    _, beats = librosa.beat.beat_track(y=signal, sr=rate, hop_length=HOP, units="frames")
    beats = np.asarray(beats, dtype=int)
    if beats.size < MIN_BEATS:
        raise InvalidValueError("No se encontró un pulso claro. Prueba con un audio más largo.")
    beat_times = librosa.frames_to_time(beats, sr=rate, hop_length=HOP)
    bpm = int(round(60.0 / float(np.median(np.diff(beat_times)))))

    harmonic = librosa.effects.harmonic(signal)
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=rate, hop_length=HOP)
    energy = librosa.feature.rms(y=signal, hop_length=HOP)
    beat_chroma = librosa.util.sync(chroma, beats, aggregate=np.median, pad=False)
    beat_energy = librosa.util.sync(energy, beats, aggregate=np.mean, pad=False)[0]

    templates, names = _templates(np)
    norms = np.linalg.norm(beat_chroma, axis=0, keepdims=True)
    similarity = templates @ (beat_chroma / np.maximum(norms, 1e-9))
    likelihood = np.exp(SHARPNESS * (similarity - similarity.max(axis=0, keepdims=True)))
    silent = beat_energy < SILENCE_RATIO * float(beat_energy.max())
    # Un estado más, "sin acorde", fuerte en los pulsos casi en silencio.
    no_chord = np.where(silent, 1.0, 1e-3)
    likelihood = np.vstack([likelihood * np.where(silent, 1e-3, 1.0), no_chord])
    likelihood /= likelihood.sum(axis=0, keepdims=True)
    transition = librosa.sequence.transition_loop(len(names) + 1, SELF_TRANSITION)
    path_states = librosa.sequence.viterbi(likelihood, transition)

    chords: list[AnalyzedChord] = []
    for beat, state in enumerate(path_states):
        if state == len(names):
            continue
        symbol = names[int(state)]
        last = chords[-1] if chords else None
        if last and last.symbol == symbol and abs(last.start + last.beats - beat) < 1e-6:
            chords[-1] = AnalyzedChord(last.start, last.beats + 1, symbol)
        else:
            chords.append(AnalyzedChord(float(beat), 1.0, symbol))
    if not chords:
        raise InvalidValueError("No se reconocieron acordes en el audio.")

    notes = _melody(librosa, np, signal, rate, beat_times) if melody else ()
    return AudioAnalysis(bpm=bpm, chords=tuple(chords), melody=notes)


def _melody(
    librosa: Any, np: Any, signal: Any, rate: int, beat_times: Any
) -> tuple[AnalyzedNote, ...]:
    """Una sola voz con pYIN. Sirve para un punteo o una melodía sola, no para una mezcla."""
    f0, voiced, _ = librosa.pyin(
        signal, fmin=82.0, fmax=1047.0, sr=rate, frame_length=2048, hop_length=HOP
    )
    times = librosa.frames_to_time(np.arange(len(f0)), sr=rate, hop_length=HOP)
    beat_axis = np.arange(len(beat_times), dtype=float)
    notes: list[AnalyzedNote] = []
    current: tuple[int, float] | None = None
    for index, (frequency, is_voiced) in enumerate(zip(f0, voiced, strict=False)):
        midi = int(round(float(librosa.hz_to_midi(frequency)))) if is_voiced else None
        if current and (midi is None or midi != current[0]):
            pitch, started = current
            ended = float(times[index])
            if ended - started >= MIN_NOTE_SECONDS and 28 <= pitch <= 100:
                start_beat = float(np.interp(started, beat_times, beat_axis))
                end_beat = float(np.interp(ended, beat_times, beat_axis))
                if end_beat > start_beat:
                    notes.append(
                        AnalyzedNote(round(start_beat, 3), round(end_beat - start_beat, 3), pitch)
                    )
            current = None
        if midi is not None and current is None:
            current = (midi, float(times[index]))
    return tuple(notes[:4000])
