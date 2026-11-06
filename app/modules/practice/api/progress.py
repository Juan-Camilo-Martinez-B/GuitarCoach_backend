"""Historial de precisión del usuario. No incluye audio."""

from typing import cast

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.modules.identity.public import bearer_user_id
from app.modules.practice.ports import PracticeStore
from app.shared.config import Settings
from app.shared.http.deps import current_uow

router = APIRouter(tags=["progress"])


class ProgressPoint(BaseModel):
    attempt_id: str
    song_id: int
    song_title: str | None
    accuracy: float
    avg_delta_ms: float
    created_at: str


@router.get("/me/progress")
async def read_progress(
    request: Request,
    authorization: str = Header(),
) -> list[ProgressPoint]:
    settings: Settings = request.app.state.settings
    uow = cast(PracticeStore, current_uow(request))
    user_id = bearer_user_id(authorization, settings)
    attempts = await uow.attempts.list_for_user(user_id)
    ordered = sorted(attempts, key=lambda item: item.created_at)
    titles: dict[int, str | None] = {}
    for song_id in {item.song_id for item in ordered}:
        song = await uow.songs.get(song_id)
        titles[song_id] = None if song is None else song.title
    return [
        ProgressPoint(
            attempt_id=str(item.id),
            song_id=item.song_id,
            song_title=titles.get(item.song_id),
            accuracy=item.accuracy,
            avg_delta_ms=item.avg_delta_ms,
            created_at=item.created_at.isoformat(),
        )
        for item in ordered
    ]
