"""Punto de entrada de la API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from fastapi import FastAPI

from app.api.middleware.database import install_database
from app.api.middleware.errors import register_exception_handlers
from app.api.middleware.rate_limit import SlidingWindowLimiter, install_auth_rate_limit
from app.api.middleware.security import install_security
from app.api.v1.attempts import router as attempts_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.lessons import router as lessons_router
from app.api.v1.progress import router as progress_router
from app.api.v1.reports import router as reports_router
from app.api.v1.songs import router as songs_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.domain.interfaces.repositories import UnitOfWork
from app.infrastructure.ai.gemini_tutor import GeminiTutor
from app.infrastructure.db.catalog import ensure_catalog
from app.infrastructure.db.memory import InMemoryUnitOfWork
from app.infrastructure.db.repositories import SqlUnitOfWork
from app.infrastructure.queue.local_dispatcher import LocalTaskDispatcher
from app.infrastructure.scraping.factory import build_importer, shared_registry


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación. Los tests pueden inyectar una configuración propia."""
    active = settings or get_settings()
    active.ensure_production_secrets()
    configure_logging(active.log_level)
    memory = InMemoryUnitOfWork()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        factory = getattr(app.state, "session_factory", None)
        if factory is None:
            await ensure_catalog(cast(UnitOfWork, memory))
        else:
            async with factory() as session:
                await ensure_catalog(cast(UnitOfWork, SqlUnitOfWork(session)))
        yield

    app = FastAPI(title=active.app_name, lifespan=lifespan)
    app.state.settings = active
    app.state.uow = memory
    registry = shared_registry()
    app.state.registry = registry
    dispatcher = LocalTaskDispatcher()

    async def run_import(payload: dict[str, str]) -> None:
        factory = getattr(app.state, "session_factory", None)
        if factory is None:
            await build_importer(cast(UnitOfWork, memory), active, registry).run(
                UUID(payload["job_id"])
            )
            return
        async with factory() as session:
            importer = build_importer(cast(UnitOfWork, SqlUnitOfWork(session)), active, registry)
            await importer.run(UUID(payload["job_id"]))

    dispatcher.register("import_song", run_import)
    app.state.dispatcher = dispatcher
    app.state.tutor = GeminiTutor(active.gemini_api_key, active.gemini_model)
    install_database(app, active)
    register_exception_handlers(app)
    install_security(app, active.cors_origins)
    install_auth_rate_limit(app, SlidingWindowLimiter(active.auth_requests_per_minute))
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(attempts_router)
    app.include_router(songs_router)
    app.include_router(reports_router)
    app.include_router(progress_router)
    app.include_router(lessons_router)
    return app


app = create_app()
