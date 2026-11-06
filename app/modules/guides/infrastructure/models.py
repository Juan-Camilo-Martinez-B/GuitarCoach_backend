"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


class SongGuideModel(Base):
    __tablename__ = "song_guides"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    song_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("songs.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    artist: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    guide: Mapped[dict[str, object]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GuideTabModel(Base):
    """El archivo va en su propia tabla: listar guías no arrastra los bytes."""

    __tablename__ = "guide_tabs"

    guide_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("song_guides.id"), primary_key=True
    )
    format: Mapped[str] = mapped_column(Text)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
