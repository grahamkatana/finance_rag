from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging import logger
from app.core.qdrant import init_qdrant
from app.features.ingestion.router import router as ingestion_router
from app.features.retrieval.router import router as retrieval_router
from app.features.generation.router import router as generation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Finance RAG API...")
    await init_qdrant()
    logger.info("Qdrant initialized")
    yield
    logger.info("Shutting down Finance RAG API...")


app = FastAPI(
    title="Finance RAG API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingestion_router)
app.include_router(retrieval_router)
app.include_router(generation_router)


@app.get("/health")
async def health():
    return {"status": "ok"}