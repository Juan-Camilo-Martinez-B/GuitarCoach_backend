"""El archivo de tablatura de una guía: con él se vuelve a tocar la canción nota por nota."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.errors import InvalidValueError

MAX_TAB_BYTES = 5 * 1024 * 1024
TAB_FORMATS = ("gp", "gp345", "gpx", "midi", "musicxml")

# GP3, GP4 y GP5 empiezan con la longitud de la versión y este texto.
_GP_LEGACY = (b"FICHIER GUITAR PRO", b"FICHIER GUITARE PRO")


def sniff_tab(raw: bytes) -> str | None:
    """Reconoce el formato por el contenido, no por la extensión que manda el cliente."""
    if raw[:4] == b"PK\x03\x04":
        # GP6 en adelante (.gp) es un ZIP con la partitura dentro.
        return "gp"
    if raw[:4] in {b"BCFZ", b"BCFS"}:
        return "gpx"
    if raw[:4] == b"MThd":
        return "midi"
    if any(raw[1 : 1 + len(magic)] == magic for magic in _GP_LEGACY):
        return "gp345"
    head = raw[:400].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"<?xml") or b"<score-partwise" in head:
        # Sin entidades: evita documentos que se expanden hasta agotar la memoria.
        return None if b"<!ENTITY" in raw else "musicxml"
    return None


@dataclass(frozen=True, slots=True)
class GuideTab:
    guide_id: UUID
    format: str
    data: bytes

    def __post_init__(self) -> None:
        if self.format not in TAB_FORMATS:
            raise InvalidValueError("Formato de tablatura desconocido.")
        if not self.data:
            raise InvalidValueError("La tablatura está vacía.")
        if len(self.data) > MAX_TAB_BYTES:
            raise InvalidValueError("La tablatura supera 5 MB.")
