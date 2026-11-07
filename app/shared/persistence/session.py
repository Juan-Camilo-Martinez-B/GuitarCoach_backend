"""Sesiones asíncronas. El esquema lo aplica el repositorio de base de datos."""

import ssl

from sqlalchemy import event
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def _supabase_ssl() -> ssl.SSLContext:
    """Cifra como sslmode=require. El pooler de Supabase no valida contra el almacén de Windows."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _asyncpg_url(database_url: str) -> str:
    """Quita parámetros de libpq. asyncpg no acepta sslmode ni channel_binding."""
    url = make_url(database_url)
    query = dict(url.query)
    query.pop("sslmode", None)
    query.pop("channel_binding", None)
    return url.set(query=query).render_as_string(hide_password=False)


def create_engine(database_url: str) -> AsyncEngine:
    remote = "localhost" not in database_url and "127.0.0.1" not in database_url
    connect_args: dict[str, object] = {}
    kwargs: dict[str, object] = {}
    if remote:
        # El pooler de Supabase, sobre todo el puerto 6543, no admite caché de sentencias.
        connect_args["ssl"] = _supabase_ssl()
        connect_args["statement_cache_size"] = 0
        kwargs["poolclass"] = NullPool
    engine = create_async_engine(_asyncpg_url(database_url), connect_args=connect_args, **kwargs)

    @event.listens_for(engine.sync_engine, "connect")
    def _use_app_schema(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO guitarcoach, public")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
