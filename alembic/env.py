import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base
from app.features.ingestion import models as ingestion_models  # noqa: F401
from app.database import models as audit_models  # noqa: F401

# Alembic Config object
config = context.config

# Setup logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 1. Tell Alembic about your models
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a DB connection.
    Useful for generating SQL scripts.
    """
    context.configure(
        url=settings.postgres_url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations with a live DB connection.
    This is what runs normally.
    """
    connectable = create_async_engine(
        settings.postgres_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# 2. Decide which mode to run
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())