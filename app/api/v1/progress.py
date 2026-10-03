"""Historial de precisión del usuario. No incluye audio."""

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.v1.attempts import _bearer_user_id
from app.core.config import Settings
from app.domain.interfaces.repositories import UnitOfWork

router = APIRouter(tags=["progress"])


class ProgressPoint(BaseModel):
    attempt_id: str
    song_id: int
    accuracy: float
    avg_delta_ms: float
    created_at: str


@router.get("/me/progress")
async def read_progress(
    request: Request,
    authorization: str = Header(),
) -> list[ProgressPoint]:
    settings: Settings = request.app.state.settings
    uow: UnitOfWork = request.app.state.uow
    user_id = _bearer_user_id(authorization, settings)
    attempts = await uow.attempts.list_for_user(user_id)
    ordered = sorted(attempts, key=lambda item: item.created_at)
    return [
        ProgressPoint(
            attempt_id=str(item.id),
            song_id=item.song_id,
            accuracy=item.accuracy,
            avg_delta_ms=item.avg_delta_ms,
            created_at=item.created_at.isoformat(),
        )
        for item in ordered
    ]
