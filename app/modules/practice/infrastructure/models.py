"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


class AttemptModel(Base):
    __tablename__ = "attempts"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    song_id: Mapped[int] = mapped_column(Integer, ForeignKey("songs.id"))
    bpm: Mapped[int] = mapped_column(Integer)
    accuracy: Mapped[float] = mapped_column(Numeric(5, 2))
    avg_delta_ms: Mapped[float] = mapped_column(Numeric(8, 2))
    latency_offset_ms: Mapped[int] = mapped_column(Integer)
    tuning_cents_avg: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    raw_summary: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChordMetricModel(Base):
    __tablename__ = "chord_metrics"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("attempts.id"))
    chord: Mapped[str] = mapped_column(Text)
    accuracy: Mapped[float] = mapped_column(Numeric(5, 2))
    avg_delta_ms: Mapped[float] = mapped_column(Numeric(8, 2))
    errors: Mapped[int] = mapped_column(Integer)
