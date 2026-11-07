"""Base declarativa común. Cada módulo declara sus propias tablas."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(schema="guitarcoach")
