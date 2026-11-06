"""Abre una sesión de PostgreSQL por petición cuando USE_DATABASE está activo."""

from collections.abc import Callable

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared.config import Settings
from app.shared.persistence.session import create_engine, create_session_factory


def install_database(
    app: FastAPI,
    settings: Settings,
    open_store: Callable[[AsyncSession], object],
) -> None:
    if not settings.use_database:
        return
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    app.state.session_factory = factory

    @app.middleware("http")
    async def database_session(request: Request, call_next: RequestResponseEndpoint) -> Response:
        async with factory() as session:
            request.state.uow = open_store(session)
            try:
                return await call_next(request)
            except Exception:
                await session.rollback()
                raise
