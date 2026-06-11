"""Dependency wiring.

The app builds its singletons once (engine, session factory, bus, channel client,
copilot, sender) in the lifespan and stashes them on `app.state`. These helpers
hand them to route functions, and `session_dep` yields one request-scoped session
that commits on success and rolls back on error — so a handler never half-writes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.copilot import Copilot
from app.core.bus import Bus
from app.core.channel_client import ChannelClient
from app.core.config import Settings
from app.infra.repo import Repo


def settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def bus_dep(request: Request) -> Bus:
    return request.app.state.bus


def channel_dep(request: Request) -> ChannelClient:
    return request.app.state.channel_client


def copilot_dep(request: Request) -> Copilot:
    return request.app.state.copilot


def session_factory_dep(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def session_dep(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def repo_dep(request: Request) -> AsyncIterator[Repo]:
    async for session in session_dep(request):
        yield Repo(session)
