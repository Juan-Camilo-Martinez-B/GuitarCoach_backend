"""La guía sobrevive en PostgreSQL y no se duplica para el mismo dueño."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from app.application.security import SystemClock
from app.application.use_cases.guides import GuideService
from app.domain.entities.user import User
from app.domain.services.guide_import import guide_from_text
from app.infrastructure.db.models import SongGuideModel, UserModel
from app.infrastructure.db.repositories import SqlUnitOfWork
from app.infrastructure.db.session import create_engine, create_session_factory
from sqlalchemy import delete

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL no está definida",
)


async def test_la_guia_se_guarda_y_se_corrige_en_postgres() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    factory = create_session_factory(engine)
    user = User(
        id=uuid4(),
        email=f"guia-{uuid4().hex[:8]}@example.com",
        display_name="Guía",
        level="beginner",
        password_hash="hash",
        oauth_subject=None,
        latency_offset_ms=0,
        created_at=SystemClock().now(),
    )
    guide = guide_from_text("[Intro]\nG D Em C", "x", title=f"SQL {user.id}", artist="Ana")
    try:
        async with factory() as session:
            uow = SqlUnitOfWork(session)
            await uow.users.add(user)
            await uow.commit()
            service = GuideService(uow, SystemClock())
            first, created = await service.create(user.id, guide, "pegado")
            again, created_again = await service.create(user.id, guide, "pegado")
            assert created and not created_again
            assert again.id == first.id

        async with factory() as session:
            service = GuideService(SqlUnitOfWork(session), SystemClock())
            stored = await service.get(user.id, first.id)
            assert stored.guide == guide
            updated = await service.update(user.id, first.id, guide, "revisada")
            assert updated.status == "revisada"
            assert len(await service.list(user.id)) == 1
    finally:
        async with factory() as session:
            await session.execute(delete(SongGuideModel).where(SongGuideModel.owner_id == user.id))
            await session.execute(delete(UserModel).where(UserModel.id == user.id))
            await session.commit()
        await engine.dispose()
