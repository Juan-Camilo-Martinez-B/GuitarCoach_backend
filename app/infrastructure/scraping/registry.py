"""Registro de scrapers. Añadir un sitio no cambia al que ya funciona."""

from app.infrastructure.scraping.base import ChordScraper


class ScraperRegistry:
    def __init__(self) -> None:
        self._scrapers: dict[str, ChordScraper] = {}

    def register(self, name: str, scraper: ChordScraper) -> None:
        self._scrapers[name] = scraper

    def get(self, name: str) -> ChordScraper:
        try:
            return self._scrapers[name]
        except KeyError as error:
            raise KeyError(f"No hay adaptador de scraping llamado {name}.") from error
