"""Canciones de práctica que existen sin scrapear sitios externos."""

from app.domain.entities.song import ChartChord, Song
from app.domain.interfaces.repositories import UnitOfWork
from app.domain.services.chart_import import build_plan
from app.domain.value_objects.bpm import Bpm
from app.domain.value_objects.chord import Chord


def _song(
    title: str,
    artist: str,
    song_key: str,
    bpm: int,
    chords: list[tuple[int, float, str]],
    source_url: str,
    content_hash: str,
) -> Song:
    return Song(
        title=title,
        artist=artist,
        song_key=song_key,
        bpm=Bpm(bpm),
        chords=tuple(ChartChord(bar, beat, Chord.parse(symbol)) for bar, beat, symbol in chords),
        source_url=source_url,
        source_name="catalogo",
        content_hash=content_hash,
    )


CATALOG = (
    _song(
        "Cambios abiertos",
        "GuitarCoach",
        "G",
        72,
        [(1, 1, "G"), (2, 1, "D"), (3, 1, "Em"), (4, 1, "C")],
        "https://guitarcoach.local/catalogo/cambios-abiertos",
        "catalogo-cambios-abiertos",
    ),
    _song(
        "Ronda de menores",
        "GuitarCoach",
        "Am",
        66,
        [(1, 1, "Am"), (2, 1, "Dm"), (3, 1, "E"), (4, 1, "Am")],
        "https://guitarcoach.local/catalogo/ronda-de-menores",
        "catalogo-ronda-de-menores",
    ),
    _song(
        "Lamento boliviano",
        "GuitarCoach",
        "Em",
        124,
        [(1, 1, "Em"), (2, 1, "Bm7"), (3, 1, "Am"), (4, 1, "Em"), (4, 3, "B7")],
        "https://guitarcoach.local/catalogo/lamento-boliviano",
        "catalogo-lamento-boliviano",
    ),
)


def _chart_matches(stored: Song, song: Song) -> bool:
    if stored.bpm.value != song.bpm.value or stored.song_key != song.song_key:
        return False
    left = tuple((chord.bar, chord.beat, chord.chord.symbol) for chord in stored.chords)
    right = tuple((chord.bar, chord.beat, chord.chord.symbol) for chord in song.chords)
    return left == right


async def ensure_catalog(uow: UnitOfWork) -> None:
    for song in CATALOG:
        stored = None
        if song.source_url:
            stored = await uow.songs.find_by_source_url(song.source_url)
        changed = stored is None or not _chart_matches(stored, song)
        if stored is None:
            stored = await uow.songs.add(song)
        elif changed and stored.id is not None:
            stored = await uow.songs.update_chart(stored.id, song)
        if stored is None or stored.id is None:
            continue
        if not changed and await uow.studies.get(stored.id) is not None:
            continue
        events = tuple((chord.bar, chord.beat, chord.chord.symbol) for chord in stored.chords)
        plan = build_plan(stored.title, stored.song_key, stored.bpm.value, events)
        await uow.studies.save(stored.id, plan)
    await uow.commit()
