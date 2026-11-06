"""Un semáforo y un intervalo mínimo por dominio externo."""

import asyncio
import time


class DomainRateLimiter:
    def __init__(self, min_interval_seconds: float, max_concurrency: int) -> None:
        self._min_interval = min_interval_seconds
        self._max_concurrency = max_concurrency
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_request: dict[str, float] = {}

    async def wait(self, domain: str) -> None:
        semaphore = self._semaphores.setdefault(domain, asyncio.Semaphore(self._max_concurrency))
        async with semaphore:
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request[domain] = time.monotonic()
