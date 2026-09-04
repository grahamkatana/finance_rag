from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import logger
from app.core.qdrant import init_qdrant
from app.features.auth.router import router as auth_router
from app.features.ingestion.router import router as ingestion_router
from app.features.retrieval.router import router as retrieval_router
from app.features.generation.router import router as generation_router
from app.features.generation.eval_router import router as eval_router
from app.features.audit.router import router as audit_router


async def seed_admin():
    """Create default admin user on startup if env vars are set and no admin exists."""
    if not all([settings.admin_email, settings.admin_username, settings.admin_password]):
        return

    from app.core.database import AsyncSessionLocal
    from app.features.auth.service import get_user_by_username, create_user

    async with AsyncSessionLocal() as db:
        existing = await get_user_by_username(settings.admin_username, db)
        if existing:
            if existing.is_admin:
                logger.info(f"Admin user '{settings.admin_username}' already exists")
            else:
                existing.is_admin = True
                await db.commit()
                logger.info(f"Promoted '{settings.admin_username}' to admin")
            return

        await create_user(
            settings.admin_email,
            settings.admin_username,
            settings.admin_password,
            db,
            is_admin=True,
        )
        await db.commit()
        logger.info(f"Seeded admin user '{settings.admin_username}'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Finance RAG API...")
    await init_qdrant()
    logger.info("Qdrant initialized")
    await seed_admin()
    yield
    logger.info("Shutting down Finance RAG API...")


app = FastAPI(
    title="Finance RAG API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(generation_router)
app.include_router(eval_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
