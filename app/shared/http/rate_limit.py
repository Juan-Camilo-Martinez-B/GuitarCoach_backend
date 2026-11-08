"""Límite de autenticación por cliente, con ventana deslizante.

Con Redis el conteo se comparte entre todas las instancias (en Vercel cada una tiene su
propia memoria). Sin Redis, o si Redis falla, cuenta solo este proceso.
"""

import logging
import math
import time
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

AUTH_KEY_PREFIX = "guitarcoach:ratelimit:auth:"
# Un login no debe quedarse esperando a un Redis lento: pasado esto, cuenta la memoria.
REDIS_TIMEOUT_SECONDS = 1.0
UNKNOWN_CLIENT = "desconocido"

Clock = Callable[[], float]


class RateLimiter(Protocol):
    async def allow(self, key: str) -> bool: ...

    async def aclose(self) -> None: ...


class MemoryRateLimiter:
    """Cuenta en este proceso. Sirve en local y como respaldo cuando Redis no responde."""

    def __init__(
        self, limit: int, window_seconds: float = 60.0, clock: Clock = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, list[float]] = {}

    async def allow(self, key: str) -> bool:
        now = self._clock()
        recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < self._window]
        if len(recent) >= self._limit:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True

    async def aclose(self) -> None:
        self._hits.clear()


class RedisRateLimiter:
    """Guarda cada intento en un sorted set por cliente, con su hora como puntaje.

    La transacción quita lo que salió de la ventana, anota el intento y cuenta, de forma
    atómica. Los intentos rechazados también cuentan: quien insiste sigue bloqueado.
    """

    def __init__(
        self,
        client: Redis,
        limit: int,
        fallback: RateLimiter,
        window_seconds: float = 60.0,
        clock: Clock = time.time,
    ) -> None:
        self._client = client
        self._limit = limit
        self._fallback = fallback
        self._window = window_seconds
        self._clock = clock

    async def allow(self, key: str) -> bool:
        now = self._clock()
        redis_key = f"{AUTH_KEY_PREFIX}{key}"
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, 0, now - self._window)
                pipe.zadd(redis_key, {f"{now}:{uuid4().hex}": now})
                pipe.zcard(redis_key)
                pipe.expire(redis_key, math.ceil(self._window))
                results = await pipe.execute()
        except Exception:
            logger.warning("Redis no responde. El límite de autenticación cuenta en memoria.")
            return await self._fallback.allow(key)
        return int(results[2]) <= self._limit

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._fallback.aclose()


def build_auth_rate_limiter(redis_url: str, limit: int) -> RateLimiter:
    """Redis si hay URL; la conexión se abre en la primera petición, no al arrancar."""
    memory = MemoryRateLimiter(limit)
    if not redis_url.strip():
        return memory
    client: Redis = Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
    )
    return RedisRateLimiter(client, limit, fallback=memory)


def client_key(request: Request, trust_proxy_headers: bool) -> str:
    """IP del cliente. Detrás de Vercel la conexión llega desde su proxy.

    Vercel reescribe x-real-ip y x-forwarded-for, así que el cliente no puede falsearlas.
    Fuera de un proxy de confianza esas cabeceras se ignoran.
    """
    if trust_proxy_headers:
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client is not None else UNKNOWN_CLIENT


def install_auth_rate_limit(
    app: FastAPI, limiter: RateLimiter, trust_proxy_headers: bool = False
) -> None:
    @app.middleware("http")
    async def limit_auth(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/auth"):
            if not await limiter.allow(client_key(request, trust_proxy_headers)):
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": "rate_limited",
                        "message": "Demasiados intentos de autenticación.",
                    },
                )
        return await call_next(request)
