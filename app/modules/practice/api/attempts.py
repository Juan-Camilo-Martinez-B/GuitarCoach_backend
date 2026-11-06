"""Recepción de la telemetría de un intento. No recibe audio."""

from typing import cast

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from app.modules.identity.public import bearer_user_id
from app.modules.practice.application.register_attempt import RegisterAttempt, TelemetryEvent
from app.modules.practice.domain.attempt_assessor import AttemptAssessor
from app.modules.practice.ports import PracticeStore
from app.shared.clock import SystemClock
from app.shared.config import Settings
from app.shared.http.deps import current_uow

router = APIRouter(tags=["attempts"])


class EventBody(BaseModel):
    bar: int = Field(ge=1)
    expected: str
    detected: str | None = None
    delta_ms: int
    confidence: float = Field(ge=0, le=1)


class AttemptBody(BaseModel):
    song_id: int = Field(ge=1)
    bpm: int
    latency_offset_ms: int = 0
    tuning_cents_avg: float | None = None
    events: list[EventBody] = Field(min_length=1)


class AttemptResponse(BaseModel):
    id: str
    accuracy: float
    avg_delta_ms: float


@router.post("/attempts", status_code=201)
async def create_attempt(
    body: AttemptBody,
    request: Request,
    authorization: str = Header(),
) -> AttemptResponse:
    settings: Settings = request.app.state.settings
    uow = cast(PracticeStore, current_uow(request))
    attempt = await RegisterAttempt(
        uow,
        AttemptAssessor(),
        SystemClock(),
        settings.hit_window_ms,
    ).execute(
        bearer_user_id(authorization, settings),
        body.song_id,
        body.bpm,
        body.latency_offset_ms,
        body.tuning_cents_avg,
        tuple(
            TelemetryEvent(
                bar=event.bar,
                expected=event.expected,
                detected=event.detected,
                delta_ms=event.delta_ms,
                confidence=event.confidence,
            )
            for event in body.events
        ),
    )
    return AttemptResponse(
        id=str(attempt.id),
        accuracy=attempt.accuracy,
        avg_delta_ms=attempt.avg_delta_ms,
    )
