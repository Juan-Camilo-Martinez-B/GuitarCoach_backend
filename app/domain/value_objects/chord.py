"""Acorde normalizado. El símbolo canónico es la identidad del acorde."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.errors import InvalidValueError

_CHORD_PATTERN = re.compile(
    r"^(?P<root>[A-G])(?P<accidental>#|b)?(?P<quality>maj7|m7|sus2|sus4|dim|aug|m|7)?$"
)


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
