"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


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


class SongStudyModel(Base):
    __tablename__ = "song_studies"

    song_id: Mapped[int] = mapped_column(Integer, ForeignKey("songs.id"), primary_key=True)
    plan: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
