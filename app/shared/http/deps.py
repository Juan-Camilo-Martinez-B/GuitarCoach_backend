"""Dependencias de petición. La sesión SQL vive en la petición, no en el proceso."""

from fastapi import Request

from app.shared.config import Settings


def current_uow(request: Request) -> object:
    """El almacén de la petición. Cada módulo lo ve solo a través de su propio puerto."""
    scoped = getattr(request.state, "uow", None)
    return scoped if scoped is not None else request.app.state.uow


def current_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    return settings
