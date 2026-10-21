"""Dependencias de petición. La sesión SQL vive en la petición, no en el proceso."""

from typing import cast

from fastapi import Request

from app.domain.interfaces.repositories import UnitOfWork


def current_uow(request: Request) -> UnitOfWork:
    scoped = getattr(request.state, "uow", None)
    if scoped is not None:
        return cast(UnitOfWork, scoped)
    return cast(UnitOfWork, request.app.state.uow)
