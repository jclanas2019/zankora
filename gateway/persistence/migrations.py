from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import AsyncEngine
from gateway.persistence.schema import Base

async def init_db(engine: AsyncEngine) -> None:
    os.makedirs(os.path.dirname(engine.url.database), exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
