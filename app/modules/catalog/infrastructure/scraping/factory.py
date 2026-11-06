"""Construye el importador con el almacén de la petición."""

from pathlib import Path

from app.modules.catalog.application.import_song import ImportSong
from app.modules.catalog.application.scraping.rate_limiter import DomainRateLimiter
from app.modules.catalog.application.scraping.registry import ScraperRegistry
from app.modules.catalog.infrastructure.scraping.open_fixture import OpenFixtureScraper
from app.modules.catalog.ports import CatalogStore
from app.shared.clock import SystemClock
from app.shared.config import Settings

SAMPLE_CHART = Path(__file__).resolve().parent / "sample_chart.html"
PERMISSIVE_ROBOTS = "User-agent: *\nAllow: /\n"
SAMPLE_SOURCE = "https://example.com/charts/muestra"


def shared_registry() -> ScraperRegistry:
    registry = ScraperRegistry()
    registry.register(
        "open-fixture",
        OpenFixtureScraper(SAMPLE_CHART.read_text(encoding="utf-8"), SAMPLE_SOURCE),
    )
    return registry


def build_importer(uow: CatalogStore, active: Settings, registry: ScraperRegistry) -> ImportSong:
    return ImportSong(
        uow,
        registry,
        DomainRateLimiter(active.scrape_min_interval_seconds, active.scrape_max_concurrency),
        SystemClock(),
        "open-fixture",
        PERMISSIVE_ROBOTS,
    )
