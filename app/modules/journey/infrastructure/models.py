"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


class JourneyMilestoneModel(Base):
    __tablename__ = "journey_milestones"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    milestone: Mapped[str] = mapped_column(Text, primary_key=True)
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PracticeDayModel(Base):
    __tablename__ = "practice_days"

    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
