"""Cola local de trabajos. Cloud Tasks puede sustituirla sin cambiar los casos de uso."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import uuid4

Handler = Callable[[dict[str, str]], Awaitable[None]]


@dataclass
class JobState:
    status: str
    error: str | None = None


class LocalTaskDispatcher:
    """Ejecuta handlers en tareas asyncio. Si una se retrasa, el cliente consulta el estado."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._jobs: dict[str, JobState] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def register(self, name: str, handler: Handler) -> None:
        self._handlers[name] = handler

    def enqueue(self, name: str, payload: dict[str, str]) -> str:
        if name not in self._handlers:
            raise KeyError(f"No hay handler para {name}.")
        job_id = str(uuid4())
        self._jobs[job_id] = JobState(status="pending")
        self._tasks[job_id] = asyncio.create_task(self._run(job_id, name, payload))
        return job_id

    def get(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    async def join(self, job_id: str) -> None:
        await self._tasks[job_id]

    async def _run(self, job_id: str, name: str, payload: dict[str, str]) -> None:
        self._jobs[job_id] = JobState(status="running")
        try:
            await self._handlers[name](payload)
        except Exception as error:
            self._jobs[job_id] = JobState(status="failed", error=str(error))
        else:
            self._jobs[job_id] = JobState(status="done")
