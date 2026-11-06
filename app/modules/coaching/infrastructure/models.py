"""Mapeo al esquema de guitarcoach-database. Este módulo no genera migraciones."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.persistence.base import Base


class ReportModel(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("attempts.id"))
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    metrics_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
