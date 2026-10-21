"""Construye el importador con el almacén de la petición."""

from pathlib import Path

from app.application.security import SystemClock
from app.application.use_cases.import_song import ImportSong
from app.core.config import Settings
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.scraping.open_fixture import OpenFixtureScraper
from app.infrastructure.scraping.rate_limiter import DomainRateLimiter
from app.infrastructure.scraping.registry import ScraperRegistry

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


def build_importer(uow: UnitOfWork, active: Settings, registry: ScraperRegistry) -> ImportSong:
    return ImportSong(
        uow,
        registry,
        DomainRateLimiter(active.scrape_min_interval_seconds, active.scrape_max_concurrency),
        SystemClock(),
        "open-fixture",
        PERMISSIVE_ROBOTS,
    )
