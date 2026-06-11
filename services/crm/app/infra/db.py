"""Async engine + session factory. One place owns the connection lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.infra.models import Base


def make_engine(database_url: str) -> AsyncEngine:
    # check_same_thread is a SQLite-only arg; harmless to pass only there.
    connect_args = {}
    kwargs: dict = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # NullPool: open a fresh connection per use. With WAL + a pooled
        # connection, a reader can hold a stale snapshot and miss rows another
        # connection just committed (seed visible to one request but not the
        # next). A fresh connection always reads the latest committed state.
        kwargs["poolclass"] = NullPool
    engine = create_async_engine(
        database_url, future=True, connect_args=connect_args, **kwargs
    )

    if database_url.startswith("sqlite"):
        # busy_timeout makes a connection wait for the write lock instead of
        # failing under concurrent writes. We deliberately do NOT enable WAL:
        # with NullPool opening a fresh connection per session, the default
        # rollback-journal mode gives straightforward read-committed visibility
        # (every new connection sees the latest commit), whereas WAL's snapshot
        # semantics let a freshly-opened connection occasionally miss a commit
        # that another connection just made.
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _rec):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
