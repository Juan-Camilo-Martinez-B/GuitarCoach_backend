"""Traduce errores de dominio a respuestas HTTP coherentes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    InvalidValueError,
    NotFoundError,
    RateLimitExceededError,
)

STATUS_BY_TYPE: dict[type[DomainError], int] = {
    InvalidValueError: 422,
    AuthenticationError: 401,
    NotFoundError: 404,
    ConflictError: 409,
    RateLimitExceededError: 429,
    ExternalServiceError: 502,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_request: Request, error: DomainError) -> JSONResponse:
        status = STATUS_BY_TYPE.get(type(error), 400)
        return JSONResponse(
            status_code=status,
            content={"code": error.code, "message": str(error)},
        )
