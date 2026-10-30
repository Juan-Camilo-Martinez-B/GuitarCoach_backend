"""Acorde normalizado. El símbolo canónico es la identidad del acorde."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import InvalidValueError

# Las alternativas largas van primero para que "m7b5" no se lea como "m".
_QUALITIES = "maj9|maj7|m7b5|m7|m6|m9|7sus4|sus2|sus4|dim7|dim|aug|add9|m|7|6|9"
_CHORD_PATTERN = re.compile(rf"^(?P<root>[A-G])(?P<accidental>#|b)?(?P<quality>{_QUALITIES})?$")
_SPANISH_ROOTS = {"Do": "C", "Re": "D", "Mi": "E", "Fa": "F", "Sol": "G", "La": "A", "Si": "B"}
# Primero la raíz inglesa: así "Fadd9" no se lee como Fa más "dd9".
_LOOSE_PATTERNS = (
    re.compile(r"^(?P<root>[A-G])(?P<accidental>#|b)?(?P<rest>.*)$"),
    re.compile(r"^(?P<root>Do|Re|Mi|Fa|Sol|La|Si)(?P<accidental>#|b)?(?P<rest>.*)$"),
)
# Cómo escriben la cualidad los cancioneros en línea, hacia el símbolo canónico.
_QUALITY_ALIASES = {
    "": "",
    "maj": "",
    "M": "",
    "min": "m",
    "mi": "m",
    "-": "m",
    "M7": "maj7",
    "Maj7": "maj7",
    "7M": "maj7",
    "Δ": "maj7",
    "Δ7": "maj7",
    "m7(b5)": "m7b5",
    "ø": "m7b5",
    "ø7": "m7b5",
    # Sin "o" como disminuido: "Do" es la nota Do, no Re disminuido.
    "°": "dim",
    "°7": "dim7",
    "+": "aug",
    "sus": "sus4",
    "(9)": "add9",
    "2": "sus2",
    "4": "sus4",
    "min7": "m7",
    "mi7": "m7",
    "-7": "m7",
}


@dataclass(frozen=True, slots=True)
class Chord:
    """Acorde de guitarra reducido a fundamental, alteración y cualidad."""

    root: str
    accidental: str
    quality: str

    @property
    def symbol(self) -> str:
        return f"{self.root}{self.accidental}{self.quality}"

    @classmethod
    def parse(cls, raw: str) -> Chord:
        match = _CHORD_PATTERN.fullmatch(raw.strip())
        if match is None:
            raise InvalidValueError(f"Acorde no reconocido: {raw}.")
        return cls(
            root=match.group("root"),
            accidental=match.group("accidental") or "",
            quality=match.group("quality") or "",
        )

    @classmethod
    def read(cls, raw: str) -> Chord | None:
        """Lee un acorde como lo escribe un cancionero: Lam, G/B, C7M. None si no lo es."""
        token = raw.strip().split("/", 1)[0]
        for pattern in _LOOSE_PATTERNS:
            match = pattern.fullmatch(token)
            if match is None:
                continue
            root = _SPANISH_ROOTS.get(match.group("root"), match.group("root"))
            rest = match.group("rest")
            quality = _QUALITY_ALIASES.get(rest, rest)
            try:
                return cls.parse(f"{root}{match.group('accidental') or ''}{quality}")
            except InvalidValueError:
                continue
        return None
