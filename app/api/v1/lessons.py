"""Temario, progreso guardado y análisis según el módulo alcanzado."""

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from app.api.deps import current_uow
from app.api.v1.attempts import _bearer_user_id
from app.application.security import SystemClock
from app.core.config import Settings
from app.domain.curriculum import LESSONS, lesson_by_id, previous_id, review_lessons
from app.domain.entities.report import ReportContent
from app.domain.errors import ConflictError, NotFoundError
from app.domain.services.training_coach import MODES, coach_prompt, local_brief
from app.infrastructure.ai.gemini_tutor import GeminiTutor

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


class CoachBody(BaseModel):
    mode: str


class CoachView(BaseModel):
    diagnostico: str
    ejercicios: list[str]
    plan_semanal: list[str]
    consejos_tecnica: list[str]
    model: str


def _settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    return settings


@router.get("/me/curriculum")
async def read_curriculum(
    request: Request,
    authorization: str = Header(),
) -> CurriculumView:
    settings = _settings(request)
    user_id = _bearer_user_id(authorization, settings)
    uow = current_uow(request)
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
    settings = _settings(request)
    user_id = _bearer_user_id(authorization, settings)
    lesson = lesson_by_id(lesson_id)
    if lesson is None:
        raise NotFoundError("Ese módulo no existe.")
    uow = current_uow(request)
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
    settings = _settings(request)
    user_id = _bearer_user_id(authorization, settings)
    uow = current_uow(request)
    await uow.lessons.mark_reviewed(user_id, SystemClock().now().date())
    await uow.commit()


@router.post("/me/coach")
async def coach(
    body: CoachBody,
    request: Request,
    authorization: str = Header(),
) -> CoachView:
    settings = _settings(request)
    user_id = _bearer_user_id(authorization, settings)
    if body.mode not in MODES:
        raise NotFoundError("El modo de análisis no existe.")
    done = set((await current_uow(request).lessons.completed(user_id)).keys())
    brief = local_brief(body.mode, done)
    tutor = request.app.state.tutor
    model = "analisis-local"
    content = brief
    if isinstance(tutor, GeminiTutor) and settings.gemini_api_key:
        content = await tutor.advise(coach_prompt(body.mode, done, brief))
        model = settings.gemini_model
    return _view(content, model)


def _view(content: ReportContent, model: str) -> CoachView:
    return CoachView(
        diagnostico=content.diagnostico,
        ejercicios=list(content.ejercicios),
        plan_semanal=list(content.plan_semanal),
        consejos_tecnica=list(content.consejos_tecnica),
        model=model,
    )
