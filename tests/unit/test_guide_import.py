"""Los lectores conservan compases, duraciones y secciones, y descartan la letra."""

import pytest
from app.domain.entities.guide import SongGuide, StrumPattern
from app.domain.errors import InvalidValueError
from app.domain.services.guide_import import guide_from_file, guide_from_musicxml, guide_from_text
from app.domain.value_objects.chord import Chord

PASTED = """Capo 2
[Intro]
G  D  Em  C  x2

[Verso 1]
G              D
Esta letra se lee pero no se guarda
Em             C
otra línea de la letra

Coro:
| Am . . . | D7 . G . | % |
"""

MUSICXML = """<?xml version="1.0"?>
<score-partwise>
  <work><work-title>Vals</work-title></work>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>2</divisions>
        <time><beats>3</beats><beat-type>4</beat-type></time>
      </attributes>
      <direction><sound tempo="96"/></direction>
      <harmony><root><root-step>A</root-step></root><kind>minor-seventh</kind></harmony>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration>
        <voice>1</voice><tie type="start"/></note>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration>
        <voice>1</voice><tie type="stop"/></note>
      <harmony><root><root-step>D</root-step></root><kind>dominant</kind></harmony>
      <note><rest/><duration>2</duration><voice>1</voice></note>
    </measure>
    <measure number="2">
      <note><pitch><step>F</step><alter>1</alter><octave>4</octave></pitch>
        <duration>6</duration><voice>1</voice></note>
    </measure>
  </part>
</score-partwise>
"""


def _chords(guide: SongGuide) -> list[tuple[float, float, str]]:
    return [(chord.start, chord.beats, chord.chord.symbol) for chord in guide.chords]


def test_el_texto_pegado_arma_secciones_y_compases_sin_la_letra() -> None:
    guide = guide_from_text(PASTED, "x", title="Prueba", artist="Ana")
    assert guide.capo == 2
    assert [section.name for section in guide.sections] == ["Intro", "Verso 1", "Coro"]
    # La intro se repite: ocho compases de cuatro pulsos.
    assert guide.sections[0].beats == 32
    assert _chords(guide)[:2] == [(0.0, 4.0, "G"), (4.0, 4.0, "D")]
    # | D7 . G . | parte el compás a la mitad y % lo repite.
    assert _chords(guide)[-4:] == [
        (52.0, 2.0, "D7"),
        (54.0, 2.0, "G"),
        (56.0, 2.0, "D7"),
        (58.0, 2.0, "G"),
    ]
    assert "letra" not in str(guide.as_dict())


def test_el_chordpro_respeta_el_compas_y_la_melodia() -> None:
    text = """{title: Patio}
{artist: Ana}
{tempo: 90}
{time: 3/4}
{start_of_chorus}
[G]Letra [D]letra
{end_of_chorus}
melody: G4 D4:2 E C
"""
    guide = guide_from_text(text, "x")
    assert (guide.title, guide.bpm.value, guide.beats_per_bar) == ("Patio", 90, 3.0)
    assert _chords(guide) == [(0.0, 3.0, "G"), (3.0, 3.0, "D")]
    assert [(note.start, note.beats, note.midi) for note in guide.melody][:2] == [
        (0.0, 1.0, 67),
        (1.0, 2.0, 62),
    ]
    assert guide.sections[0].name == "Coro"


def test_lee_acordes_en_espanol_y_el_rasgueo_en_casilleros() -> None:
    guide = guide_from_text("Lam  Rem  Mi7  Sol/Si", "x", strum="D-DU-UDU")
    assert [chord.chord.symbol for chord in guide.chords] == ["Am", "Dm", "E7", "G"]
    strum = guide.sections[0].strum
    assert strum.directions == ("abajo", "abajo", "arriba", "arriba", "abajo", "arriba")
    assert strum.beats == (1.0, 0.5, 1.0, 0.5, 0.5, 0.5)


def test_rechaza_un_texto_sin_acordes() -> None:
    with pytest.raises(InvalidValueError):
        guide_from_text("Solo letra, nada de acordes por aquí.", "x")


def test_el_musicxml_respeta_duraciones_ligaduras_y_silencios() -> None:
    guide = guide_from_musicxml(MUSICXML, "x")
    assert (guide.title, guide.bpm.value, guide.beats_per_bar) == ("Vals", 96, 3.0)
    assert _chords(guide) == [(0.0, 2.0, "Am7"), (2.0, 4.0, "D7")]
    # Las dos La ligadas son una sola nota; el silencio corre el Fa# al compás 2.
    assert [(note.start, note.beats, note.midi) for note in guide.melody] == [
        (0.0, 2.0, 69),
        (3.0, 3.0, 66),
    ]


def test_el_musicxml_no_admite_entidades() -> None:
    with pytest.raises(InvalidValueError):
        guide_from_musicxml('<!DOCTYPE x [<!ENTITY a "b">]><score-partwise/>', "x")


def test_el_archivo_elige_el_lector_por_la_extension() -> None:
    _, kind = guide_from_file("vals.musicxml", MUSICXML.encode())
    assert kind == "musicxml"
    _, kind = guide_from_file("patio.cho", b"[G] [D]")
    assert kind == "chordpro"
    with pytest.raises(InvalidValueError):
        guide_from_file("grande.cho", b"x" * 200_001)


def test_la_guia_rechaza_la_letra_y_las_secciones_superpuestas() -> None:
    document = guide_from_text("G D", "x").as_dict()
    with pytest.raises(InvalidValueError):
        SongGuide.from_dict({**document, "lyrics": "la la la"})
    overlapping = {
        **document,
        "sections": [
            {"name": "A", "start": 0, "beats": 8, "strum": {"directions": ["abajo"], "beats": [4]}},
            {"name": "B", "start": 4, "beats": 4, "strum": {"directions": ["abajo"], "beats": [4]}},
        ],
    }
    with pytest.raises(InvalidValueError):
        SongGuide.from_dict(overlapping)


def test_la_guia_ida_y_vuelta_conserva_el_contenido() -> None:
    guide = guide_from_text(PASTED, "x", title="Prueba", artist="Ana")
    again = SongGuide.from_dict(guide.as_dict())
    assert again == guide
    assert again.digest() == guide.digest()


def test_la_carta_plana_cuenta_compas_y_pulso_desde_uno() -> None:
    guide = guide_from_text("| G . D . |", "x")
    assert [(chord.bar, chord.beat, chord.chord.symbol) for chord in guide.chart()] == [
        (1, 1.0, "G"),
        (1, 3.0, "D"),
    ]


def test_el_rasgueo_no_empieza_con_silencio() -> None:
    with pytest.raises(InvalidValueError):
        StrumPattern.from_text("-DU", 4)


@pytest.mark.parametrize(
    ("raw", "symbol"),
    [
        ("Do", "C"),
        ("Dom", "Cm"),
        ("Lam", "Am"),
        ("Sol/Si", "G"),
        ("Fadd9", "Fadd9"),
        ("C7M", "Cmaj7"),
        ("Bm7(b5)", "Bm7b5"),
        ("Esus", "Esus4"),
    ],
)
def test_lee_acordes_como_los_escriben_los_cancioneros(raw: str, symbol: str) -> None:
    chord = Chord.read(raw)
    assert chord is not None and chord.symbol == symbol


@pytest.mark.parametrize("raw", ["Verso", "x2", "la", "Hm"])
def test_no_confunde_palabras_con_acordes(raw: str) -> None:
    assert Chord.read(raw) is None
