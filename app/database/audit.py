from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# NullPool on purpose. The Celery tasks that use this engine each call
# asyncio.run(), i.e. each runs in its own event loop, and an asyncpg
# connection only works on the loop that created it. A pooled connection
# handed to the next task fails with "another operation is in progress", so
# every session opens its own connection and closes it when done.
audit_engine = create_async_engine(
    settings.postgres_url,
    poolclass=NullPool,
)

AuditSessionLocal = async_sessionmaker(
    bind=audit_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_audit_session():
    async with AuditSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise