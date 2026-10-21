"""Abre una sesión de PostgreSQL por petición cuando USE_DATABASE está activo."""

from fastapi import FastAPI
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.infrastructure.db.repositories import SqlUnitOfWork
from app.infrastructure.db.session import create_engine, create_session_factory


def install_database(app: FastAPI, settings: Settings) -> None:
    if not settings.use_database:
        return
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    app.state.session_factory = factory

    @app.middleware("http")
    async def database_session(request: Request, call_next: RequestResponseEndpoint) -> Response:
        async with factory() as session:
            request.state.uow = SqlUnitOfWork(session)
            try:
                return await call_next(request)
            except Exception:
                await session.rollback()
                raise
