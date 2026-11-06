"""Temario, progreso guardado y análisis según el módulo alcanzado."""

from typing import cast

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.modules.identity.public import bearer_user_id
from app.modules.learning.domain.curriculum import (
    LESSONS,
    lesson_by_id,
    previous_id,
    review_lessons,
)
from app.modules.learning.ports import LearningStore
from app.shared.clock import SystemClock
from app.shared.errors import ConflictError, NotFoundError
from app.shared.http.deps import current_settings, current_uow

router = APIRouter(tags=["lessons"])


class LessonView(BaseModel):
    id: str
    title: str
    summary: str
    points: list[str]
    song_title: str | None
    status: str
    locked: bool


class ReviewView(BaseModel):
    title: str
    points: list[str]


class CurriculumView(BaseModel):
    needs_review: bool
    review: list[ReviewView]
    lessons: list[LessonView]


@router.get("/me/curriculum")
async def read_curriculum(
    request: Request,
    authorization: str = Header(),
) -> CurriculumView:
    settings = current_settings(request)
    user_id = bearer_user_id(authorization, settings)
    uow = cast(LearningStore, current_uow(request))
    done = await uow.lessons.completed(user_id)
    today = SystemClock().now().date()
    needs = bool(done) and max(done.values()).date() < today
    if needs and await uow.lessons.reviewed_on(user_id, today):
        needs = False
    lessons: list[LessonView] = []
    for lesson in LESSONS:
        previous = previous_id(lesson.id)
        locked = previous is not None and previous not in done
        lessons.append(
            LessonView(
                id=lesson.id,
                title=lesson.title,
                summary=lesson.summary,
                points=list(lesson.points),
                song_title=lesson.song_title,
                status="completed" if lesson.id in done else "pending",
                locked=locked,
            )
        )
    review = [
        ReviewView(title=item.title, points=list(item.points[:2]))
        for item in review_lessons(set(done))
    ]
    return CurriculumView(needs_review=needs, review=review if needs else [], lessons=lessons)


@router.post("/me/lessons/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: str,
    request: Request,
    authorization: str = Header(),
) -> LessonView:
    settings = current_settings(request)
    user_id = bearer_user_id(authorization, settings)
    lesson = lesson_by_id(lesson_id)
    if lesson is None:
        raise NotFoundError("Ese módulo no existe.")
    uow = cast(LearningStore, current_uow(request))
    done = await uow.lessons.completed(user_id)
    today = SystemClock().now().date()
    if (
        done
        and max(done.values()).date() < today
        and not await uow.lessons.reviewed_on(user_id, today)
    ):
        raise ConflictError("Haz el repaso rápido antes de seguir.")
    previous = previous_id(lesson_id)
    if previous is not None and previous not in done:
        raise ConflictError("Termina el módulo anterior antes de seguir.")
    when = SystemClock().now()
    await uow.lessons.mark_completed(user_id, lesson_id, when)
    await uow.commit()
    return LessonView(
        id=lesson.id,
        title=lesson.title,
        summary=lesson.summary,
        points=list(lesson.points),
        song_title=lesson.song_title,
        status="completed",
        locked=False,
    )


@router.post("/me/review", status_code=204)
async def acknowledge_review(request: Request, authorization: str = Header()) -> None:
    settings = current_settings(request)
    user_id = bearer_user_id(authorization, settings)
    uow = cast(LearningStore, current_uow(request))
    await uow.lessons.mark_reviewed(user_id, SystemClock().now().date())
    await uow.commit()
