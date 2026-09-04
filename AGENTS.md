# Agents.md — Project Instructions for AI Agents

## Project Overview

Finance RAG API — a Retrieval-Augmented Generation system for financial document analysis. FastAPI + Qdrant + PostgreSQL + Celery.

## Rules

### Every feature MUST include tests

When writing or modifying any feature (new router, new service, new model, new endpoint), you MUST also write tests for it. This is non-negotiable.

- Router tests go in `tests/features/<feature>/test_router.py`
- Service tests go in `tests/features/<feature>/test_service.py`
- Core module tests go in `tests/core/<module>/test_<name>.py`
- Follow existing test patterns (see below)

If you write code without tests, you have not finished the task.

### Test conventions

- Framework: `pytest` + `pytest-asyncio`
- HTTP testing: `httpx.AsyncClient` with `ASGITransport(app=app)`
- Mocking: `unittest.mock.patch` and `AsyncMock`
- All external dependencies (DB, Qdrant, Redis, LLM providers) are mocked in tests
- Auth is globally bypassed via `app.dependency_overrides[get_current_user]` in `tests/conftest.py`
- Celery tasks are globally mocked in `tests/conftest.py` to prevent Redis connections
- Tests must pass with: `uv run pytest tests/ -v --timeout=30`
- No running server, database, or model inference required

Example router test pattern:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.fixture
def mock_deps():
    with patch("app.features.<feature>.router.get_db") as mock_db:
        mock_db.return_value = AsyncMock()
        yield


@pytest.mark.asyncio
async def test_endpoint_returns_200(mock_deps):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/<feature>/endpoint")
    assert response.status_code == 200
```

### Notes folder

Every significant work item gets a note file in `notes/`. Naming: `NNN-short-description.md`. Each note contains:
- Goal / problem statement
- Plan with numbered steps
- Files changed list
- Key decisions

## Architecture

```
app/
├── core/           Config, database, auth, LLM connector, logging, prompts
├── database/       Audit models and session factory
├── tasks/          Celery background tasks
└── features/
    ├── auth/       Register, login, JWT tokens, user model
    ├── ingestion/  PDF upload, chunking, embedding, storage
    ├── retrieval/  Hybrid search (Qdrant + Postgres FTS + RRF)
    ├── generation/ RAG streaming + LLM-as-judge eval
    └── audit/      Query and ingestion audit trail
```

## Code conventions

- Python 3.14, `uv` for dependency management
- SQLAlchemy async with `asyncpg`
- Pydantic v2 for schemas and settings
- FastAPI dependency injection for DB sessions and auth
- Alembic for migrations (revision-based, async)
- `pydantic-settings` for config from `.env`
- Logs to `storage/logs/` with rotating file handler
- Celery with Redis broker for background jobs

## Running

```bash
docker compose up -d          # Postgres, Qdrant, Redis
alembic upgrade head          # Run migrations
uvicorn app.main:app --reload # API on :8000
celery -A app.core.celery worker --loglevel=info --pool=solo  # Windows
```

## Testing

```bash
uv run pytest tests/ -v --timeout=30
```

All tests mock external dependencies. No server or DB needed.
