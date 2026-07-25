from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.qdrant import init_qdrant
from app.features.ingestion.router import router as ingestion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_qdrant()
    yield


app = FastAPI(
    title="Finance RAG API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingestion_router)


@app.get("/health")
async def health():
    return {"status": "ok"}