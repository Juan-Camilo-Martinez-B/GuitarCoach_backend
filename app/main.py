"""Punto de entrada de la API."""

from pathlib import Path
from typing import cast
from uuid import UUID

from fastapi import FastAPI

from app.api.middleware.errors import register_exception_handlers
from app.api.v1.attempts import router as attempts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.songs import router as songs_router
from app.application.security import SystemClock
from app.application.use_cases.import_song import ImportSong
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.db.memory import InMemoryUnitOfWork
from app.infrastructure.queue.local_dispatcher import LocalTaskDispatcher
from app.infrastructure.scraping.open_fixture import OpenFixtureScraper
from app.infrastructure.scraping.rate_limiter import DomainRateLimiter
from app.infrastructure.scraping.registry import ScraperRegistry

SAMPLE_CHART = Path(__file__).resolve().parent / "infrastructure" / "scraping" / "sample_chart.html"
PERMISSIVE_ROBOTS = "User-agent: *\nAllow: /\n"
SAMPLE_SOURCE = "https://example.com/charts/muestra"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación. Los tests pueden inyectar una configuración propia."""
    active = settings or get_settings()
    active.ensure_production_secrets()
    configure_logging(active.log_level)
    app = FastAPI(title=active.app_name)
    app.state.settings = active
    uow = InMemoryUnitOfWork()
    app.state.uow = uow
    registry = ScraperRegistry()
    registry.register(
        "open-fixture",
        OpenFixtureScraper(SAMPLE_CHART.read_text(encoding="utf-8"), SAMPLE_SOURCE),
    )
    importer = ImportSong(
        cast(UnitOfWork, uow),
        registry,
        DomainRateLimiter(active.scrape_min_interval_seconds, active.scrape_max_concurrency),
        SystemClock(),
        "open-fixture",
        PERMISSIVE_ROBOTS,
    )
    dispatcher = LocalTaskDispatcher()

    async def run_import(payload: dict[str, str]) -> None:
        await importer.run(UUID(payload["job_id"]))

    dispatcher.register("import_song", run_import)
    app.state.importer = importer
    app.state.dispatcher = dispatcher
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(attempts_router)
    app.include_router(songs_router)
    return app


app = create_app()
