from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.qdrant import init_qdrant


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_qdrant()
    yield
    # Shutdown (nothing to clean up yet)


app = FastAPI(
    title="Finance RAG API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}