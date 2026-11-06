"""Límites compartidos del dominio. Evitan números mágicos en las reglas."""

MIN_BPM = 20
MAX_BPM = 300
MIN_ACCURACY = 0.0
MAX_ACCURACY = 100.0
MIN_LATENCY_OFFSET_MS = -500
MAX_LATENCY_OFFSET_MS = 500
MIN_HERTZ = 20.0
MAX_HERTZ = 5_000.0
A4_MIDI = 69
A4_HERTZ = 440.0
CENTS_PER_OCTAVE = 1_200.0
SEMITONES_PER_OCTAVE = 12
DEFAULT_HIT_WINDOW_MS = 150
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
SKILL_LEVELS = ("beginner", "intermediate", "advanced")
JOB_STATUSES = ("pending", "running", "done", "failed")
