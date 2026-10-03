"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text)
    oauth_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_offset_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SongModel(Base):
    __tablename__ = "songs"

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    artist: Mapped[str] = mapped_column(Text)
    song_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    bpm: Mapped[int] = mapped_column(Integer)
    chords: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("attempts.id"))
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    metrics_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScrapeJobModel(Base):
    __tablename__ = "scrape_jobs"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    song_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("songs.id"), nullable=True)
    status: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
