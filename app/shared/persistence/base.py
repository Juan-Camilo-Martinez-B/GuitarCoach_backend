"""Base declarativa común. Cada módulo declara sus propias tablas."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
