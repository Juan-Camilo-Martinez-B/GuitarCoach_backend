"""El formato de la tablatura se reconoce por los bytes, no por la extensión."""

from uuid import uuid4

import pytest
from app.domain.entities.guide_tab import MAX_TAB_BYTES, GuideTab, sniff_tab
from app.domain.errors import InvalidValueError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"\x18FICHIER GUITAR PRO v5.00", "gp345"),
        (b"\x14FICHIER GUITARE PRO v3.00", "gp345"),
        (b"BCFZ\x00\x00", "gpx"),
        (b"PK\x03\x04\x14\x00", "gp"),
        (b"MThd\x00\x00\x00\x06", "midi"),
        (b'\xef\xbb\xbf<?xml version="1.0"?><score-partwise>', "musicxml"),
        (b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><score-partwise>', None),
        (b"%PDF-1.7", None),
        (b"", None),
    ],
)
def test_reconoce_el_formato(raw: bytes, expected: str | None) -> None:
    assert sniff_tab(raw) == expected


def test_rechaza_archivos_vacios_enormes_o_de_formato_desconocido() -> None:
    with pytest.raises(InvalidValueError):
        GuideTab(uuid4(), "gp345", b"")
    with pytest.raises(InvalidValueError):
        GuideTab(uuid4(), "gp345", b"x" * (MAX_TAB_BYTES + 1))
    with pytest.raises(InvalidValueError):
        GuideTab(uuid4(), "pdf", b"x")
