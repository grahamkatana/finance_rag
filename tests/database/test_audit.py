from sqlalchemy.pool import NullPool

from app.database.audit import audit_engine


def test_audit_engine_does_not_pool_connections():
    """Each Celery audit task runs in its own event loop (asyncio.run), and an asyncpg
    connection can't be reused across loops -- a pooled one breaks every task after the first."""
    assert isinstance(audit_engine.pool, NullPool)
