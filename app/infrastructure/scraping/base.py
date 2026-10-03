"""Pipeline de scraping. Cada sitio solo redefine búsqueda, descarga y parseo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities.song import ChartChord


@dataclass(frozen=True, slots=True)
class ParsedChart:
    title: str
    artist: str
    song_key: str | None
    bpm: int
    chords: tuple[ChartChord, ...]
    source_url: str
    source_name: str


class ChordScraper(ABC):
    """Template Method: buscar, descargar, parsear y normalizar, en ese orden."""

    def collect(self, query: str) -> ParsedChart:
        location = self.search(query)
        html = self.download(location)
        return self.normalize(self.parse(html, location))

    @abstractmethod
    def search(self, query: str) -> str: ...

    @abstractmethod
    def download(self, location: str) -> str: ...

    @abstractmethod
    def parse(self, html: str, location: str) -> ParsedChart: ...

    def normalize(self, parsed: ParsedChart) -> ParsedChart:
        title = " ".join(parsed.title.split())
        artist = " ".join(parsed.artist.split())
        return ParsedChart(
            title=title,
            artist=artist,
            song_key=parsed.song_key,
            bpm=parsed.bpm,
            chords=parsed.chords,
            source_url=parsed.source_url,
            source_name=parsed.source_name,
        )
