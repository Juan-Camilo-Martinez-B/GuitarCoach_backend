"""Ventana deslizante para no bloquear a todo el proceso, solo a una clave."""

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < self._window]
        if len(recent) >= self._limit:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True


def install_auth_rate_limit(app: FastAPI, limiter: SlidingWindowLimiter) -> None:
    @app.middleware("http")
    async def limit_auth(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/auth"):
            host = request.client.host if request.client is not None else "desconocido"
            if not limiter.allow(host, time.monotonic()):
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": "rate_limited",
                        "message": "Demasiados intentos de autenticación.",
                    },
                )
        return await call_next(request)
