"""Los lectores conservan compases, duraciones y secciones, y descartan la letra."""

import pytest
from app.domain.entities.guide import SongGuide, StrumPattern
from app.domain.errors import InvalidValueError
from app.domain.services.guide_import import (
    guide_from_file,
    guide_from_musicxml,
    guide_from_text,
)
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


def test_sin_rasgueo_cada_seccion_cuenta_un_golpe_por_tiempo() -> None:
    guide = guide_from_text(
        "{comment: Tempo 102}\n[Intro]\nAm\n[Verse]\nG\n[Chorus]\nC\n",
        "x",
    )
    assert guide.bpm.value == 102
    by_name = {section.name: section.strum for section in guide.sections}
    assert by_name["Intro"].beats == (1.0, 1.0, 0.5, 0.5, 1.0)
    assert by_name["Verse"].beats == by_name["Chorus"].beats == by_name["Intro"].beats
    assert {event.origin for event in guide.events} == {"leccion"}
    assert [(chord.chord.symbol, chord.beats) for chord in guide.chords] == [
        ("Am", 4.0),
        ("G", 4.0),
        ("C", 4.0),
    ]
    # Sin notas escritas no se inventa una melodía.
    assert guide.melody == ()


def test_el_casillero_vacio_es_aire_y_no_se_inventa_el_fraseo() -> None:
    guide = guide_from_text("Am G C", "x", strum="D-DU-UDU")
    contacts = [event.contact for event in guide.events if event.pulse < 4]
    assert contacts == ["golpe", "aire", "golpe", "golpe", "aire", "golpe", "golpe", "golpe"]
    assert {event.origin for event in guide.events} == {"escrito"}
    plain = guide_from_text("[Verse]\nAm G C\n[Chorus]\nC", "x")
    assert {event.origin for event in plain.events} == {"leccion"}
    assert [event.span for event in plain.events if event.pulse < 4] == [1.0, 1.0, 0.5, 0.5, 1.0]


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
    assert [(event.pulse, event.span, event.origin) for event in guide.events] == [
        (0.0, 2.0, "escrito"),
        (2.0, 4.0, "escrito"),
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


def test_una_guia_vieja_se_materializa_al_leerla() -> None:
    raw = guide_from_text("G", "x").as_dict()
    raw["version"] = 1
    raw.pop("events")
    raw.pop("tempo")
    again = SongGuide.from_dict(raw)
    assert again.tempo[0].pulse == 0.0
    assert again.events
    assert again.events[0].origin == "escrito"


def _score(parts: str, part_list: str = "") -> str:
    return f"""<?xml version="1.0"?>
<score-partwise>
  <part-list>{part_list}</part-list>
  {parts}
</score-partwise>
"""


def _note(step: str, octave: int, extra: str = "") -> str:
    return (
        f"<note><pitch><step>{step}</step><octave>{octave}</octave></pitch>"
        f"<duration>4</duration><voice>1</voice>{extra}</note>"
    )


def test_la_guitarra_escrita_suena_una_octava_abajo() -> None:
    attributes = (
        "<attributes><divisions>1</divisions>"
        "<transpose><diatonic>0</diatonic><chromatic>0</chromatic>"
        "<octave-change>-1</octave-change></transpose></attributes>"
    )
    xml = _score(f'<part id="P1"><measure number="1">{attributes}{_note("E", 5)}</measure></part>')
    guide = guide_from_musicxml(xml, "x")
    assert [note.midi for note in guide.melody] == [64]


def test_la_tablatura_da_la_altura_que_suena() -> None:
    tuning = "".join(
        f'<staff-tuning line="{line}"><tuning-step>{step}</tuning-step>'
        f"<tuning-octave>{octave}</tuning-octave></staff-tuning>"
        for line, (step, octave) in enumerate(
            [("E", 2), ("A", 2), ("D", 3), ("G", 3), ("B", 3), ("E", 4)], start=1
        )
    )
    attributes = (
        "<attributes><divisions>1</divisions>"
        f"<staff-details><staff-lines>6</staff-lines>{tuning}<capo>2</capo></staff-details>"
        "</attributes>"
    )
    # Escrita mal a propósito: manda la cuerda y el traste. Tercera cuerda, traste 2, cejilla 2.
    tab = "<notations><technical><string>3</string><fret>2</fret></technical></notations>"
    xml = _score(
        f'<part id="P1"><measure number="1">{attributes}{_note("C", 6, tab)}</measure></part>'
    )
    guide = guide_from_musicxml(xml, "x")
    assert [note.midi for note in guide.melody] == [55 + 2 + 2]


def test_se_elige_la_parte_de_guitarra() -> None:
    part_list = (
        '<score-part id="P1"><part-name>Voz</part-name></score-part>'
        '<score-part id="P2"><part-name>Guitarra acústica</part-name></score-part>'
    )
    attributes = "<attributes><divisions>1</divisions></attributes>"
    xml = _score(
        f'<part id="P1"><measure number="1">{attributes}{_note("C", 5)}</measure></part>'
        f'<part id="P2"><measure number="1">{attributes}{_note("G", 3)}</measure></part>',
        part_list,
    )
    guide = guide_from_musicxml(xml, "x")
    assert [note.midi for note in guide.melody] == [55]


def test_las_repeticiones_y_casillas_se_despliegan() -> None:
    attributes = "<attributes><divisions>1</divisions></attributes>"
    forward = '<barline location="left"><repeat direction="forward"/></barline>'
    first = (
        '<barline location="left"><ending number="1" type="start"/></barline>'
        '<barline location="right"><ending number="1" type="stop"/>'
        '<repeat direction="backward"/></barline>'
    )
    second = (
        '<barline location="left"><ending number="2" type="start"/></barline>'
        '<barline location="right"><ending number="2" type="discontinue"/></barline>'
    )
    xml = _score(
        '<part id="P1">'
        f'<measure number="1">{attributes}{forward}{_note("C", 4)}</measure>'
        f'<measure number="2">{first}{_note("D", 4)}</measure>'
        f'<measure number="3">{second}{_note("E", 4)}</measure>'
        f'<measure number="4">{_note("F", 4)}</measure>'
        "</part>"
    )
    guide = guide_from_musicxml(xml, "x")
    # C D | C E | F: la casilla 1 suena la primera vez y la 2 la segunda.
    assert [note.midi for note in guide.melody] == [60, 62, 60, 64, 65]
    assert [note.start for note in guide.melody] == [0.0, 4.0, 8.0, 12.0, 16.0]
