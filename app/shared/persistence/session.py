"""Sesiones asíncronas. El esquema lo aplica el repositorio de base de datos."""

import ssl

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _supabase_ssl() -> ssl.SSLContext:
    """Cifra como sslmode=require. El pooler de Supabase no valida contra el almacén de Windows."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def create_engine(database_url: str) -> AsyncEngine:
    remote = "localhost" not in database_url and "127.0.0.1" not in database_url
    connect_args = {"ssl": _supabase_ssl()} if remote else {}
    engine = create_async_engine(database_url, connect_args=connect_args)

    @event.listens_for(engine.sync_engine, "connect")
    def _use_app_schema(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO guitarcoach, public")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
