"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


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
