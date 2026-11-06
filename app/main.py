"""Punto de entrada de la API: la composición del monolito modular."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from fastapi import FastAPI

from app.bootstrap.unit_of_work import InMemoryUnitOfWork, SqlUnitOfWork
from app.modules.catalog.api.realtime import router as realtime_router
from app.modules.catalog.api.songs import router as songs_router
from app.modules.catalog.infrastructure.realtime.bus import (
    EventBus,
    MemoryEventBus,
    announce_job,
    open_event_bus,
)
from app.modules.catalog.infrastructure.scraping.factory import build_importer, shared_registry
from app.modules.catalog.infrastructure.seed import ensure_catalog
from app.modules.catalog.ports import CatalogStore
from app.modules.coaching.api.coach import router as coach_router
from app.modules.coaching.api.reports import router as reports_router
from app.modules.coaching.infrastructure.groq_tutor import GroqTutor
from app.modules.guides.api import router as guides_router
from app.modules.identity.api import router as auth_router
from app.modules.journey.api import router as journey_router
from app.modules.learning.api import router as lessons_router
from app.modules.practice.api.attempts import router as attempts_router
from app.modules.practice.api.progress import router as progress_router
from app.shared.config import Settings, get_settings
from app.shared.http.database import install_database
from app.shared.http.errors import register_exception_handlers
from app.shared.http.health import router as health_router
from app.shared.http.rate_limit import SlidingWindowLimiter, install_auth_rate_limit
from app.shared.http.security import install_security
from app.shared.logging import configure_logging
from app.shared.tasks.local_dispatcher import LocalTaskDispatcher


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación. Los tests pueden inyectar una configuración propia."""
    active = settings or get_settings()
    active.ensure_production_secrets()
    configure_logging(active.log_level)
    memory = InMemoryUnitOfWork()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        bus = await open_event_bus(active.redis_url)
        app.state.events = bus
        try:
            factory = getattr(app.state, "session_factory", None)
            if factory is None:
                await ensure_catalog(cast(CatalogStore, memory))
            else:
                async with factory() as session:
                    await ensure_catalog(cast(CatalogStore, SqlUnitOfWork(session)))
            yield
        finally:
            await bus.aclose()

    app = FastAPI(title=active.app_name, lifespan=lifespan)
    app.state.settings = active
    app.state.uow = memory
    app.state.events = MemoryEventBus()
    registry = shared_registry()
    app.state.registry = registry
    dispatcher = LocalTaskDispatcher()

    async def run_import(payload: dict[str, str]) -> None:
        job_id = UUID(payload["job_id"])

        async def execute(uow: CatalogStore) -> None:
            try:
                await build_importer(uow, active, registry).run(job_id)
            finally:
                job = await uow.jobs.get(job_id)
                if job is not None:
                    await announce_job(cast(EventBus, app.state.events), job)

        factory = getattr(app.state, "session_factory", None)
        if factory is None:
            await execute(cast(CatalogStore, memory))
            return
        async with factory() as session:
            await execute(cast(CatalogStore, SqlUnitOfWork(session)))

    dispatcher.register("import_song", run_import)
    app.state.dispatcher = dispatcher
    app.state.tutor = GroqTutor(active.groq_api_key, active.groq_model)
    install_database(app, active, SqlUnitOfWork)
    register_exception_handlers(app)
    install_security(app, active.cors_origins)
    install_auth_rate_limit(app, SlidingWindowLimiter(active.auth_requests_per_minute))
    for router in (
        health_router,
        auth_router,
        attempts_router,
        songs_router,
        reports_router,
        progress_router,
        lessons_router,
        coach_router,
        guides_router,
        journey_router,
        realtime_router,
    ):
        app.include_router(router)
    return app


app = create_app()
