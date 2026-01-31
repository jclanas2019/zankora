from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker, AsyncSession
from gateway.config import Settings

def make_engine(settings: Settings) -> AsyncEngine:
    url = f"sqlite+aiosqlite:///{settings.sqlite_path}"
    return create_async_engine(url, future=True, echo=False)

def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
