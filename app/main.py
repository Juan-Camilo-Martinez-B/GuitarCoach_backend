"""Punto de entrada de la API."""

from fastapi import FastAPI

from app.api.middleware.errors import register_exception_handlers
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación. Los tests pueden inyectar una configuración propia."""
    active = settings or get_settings()
    active.ensure_production_secrets()
    configure_logging(active.log_level)
    app = FastAPI(title=active.app_name)
    app.state.settings = active
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
