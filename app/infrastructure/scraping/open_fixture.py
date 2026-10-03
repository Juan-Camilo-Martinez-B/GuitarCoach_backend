"""Adaptador de un HTML de prueba con licencia de fixture. No llama a sitios reales."""

from selectolax.parser import HTMLParser

from app.domain.entities.song import ChartChord
from app.domain.value_objects.chord import Chord
from app.infrastructure.scraping.base import ChordScraper, ParsedChart


class OpenFixtureScraper(ChordScraper):
    """Lee una página ya descargada. Sirve para pruebas y como modelo de un adaptador real."""

    def __init__(self, html: str, source_url: str, source_name: str = "open-fixture") -> None:
        self._html = html
        self._source_url = source_url
        self._source_name = source_name

    def search(self, query: str) -> str:
        del query
        return self._source_url

    def download(self, location: str) -> str:
        del location
        return self._html

    def parse(self, html: str, location: str) -> ParsedChart:
        tree = HTMLParser(html)
        title = _text(tree, "h1")
        artist = _text(tree, ".artist")
        bpm = int(_text(tree, ".bpm"))
        key_node = tree.css_first(".key")
        song_key = key_node.text(strip=True) if key_node is not None else None
        chords: list[ChartChord] = []
        for node in tree.css("ol.chords li"):
            attributes = node.attributes
            chords.append(
                ChartChord(
                    bar=int(attributes.get("data-bar") or "0"),
                    beat=float(attributes.get("data-beat") or "0"),
                    chord=Chord.parse(node.text(strip=True)),
                )
            )
        return ParsedChart(
            title=title,
            artist=artist,
            song_key=song_key,
            bpm=bpm,
            chords=tuple(chords),
            source_url=location,
            source_name=self._source_name,
        )


def _text(tree: HTMLParser, selector: str) -> str:
    node = tree.css_first(selector)
    if node is None:
        raise ValueError(f"El HTML no tiene {selector}.")
    return node.text(strip=True)
