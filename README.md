# Finance RAG API

A production-grade Retrieval-Augmented Generation (RAG) system for financial document analysis. Built with FastAPI, Qdrant, PostgreSQL hybrid search, Ollama for fully local LLM inference, Authentik for authentication, and Celery for background audit processing.

---

## What It Does

Upload financial PDFs (SEC 10-K filings, earnings reports) and ask natural language questions. The system retrieves the most relevant chunks using hybrid search, streams a grounded answer citing the exact source, and logs every interaction for audit purposes.

```
PDF Upload → Chunk → Embed → Store (Qdrant + Postgres)
Query → Authenticate → Embed → Hybrid Search (Dense + BM25 + RRF) → Stream Answer → Audit
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL (BM25 via tsvector) |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| LLM + Embeddings | Ollama (local) |
| Embedding Model | nomic-embed-text (768 dims) or all-minilm (384 dims) |
| Generation Model | phi4-mini or llama3.2 |
| Judge Model | gemma3:4b |
| Auth | Authentik (OAuth2/OIDC) |
| Background Jobs | Celery + Redis |
| Job Monitoring | Flower |
| Dependency Management | uv |
| Testing | pytest + pytest-asyncio |

---

## Architecture

```
app/
├── core/
│   ├── config.py         # Typed settings via pydantic-settings
│   ├── database.py       # Async SQLAlchemy engine + session
│   ├── qdrant.py         # Qdrant client + collection init
│   ├── logging.py        # Daily rotating file logger
│   ├── auth.py           # JWT validation via Authentik JWKS
│   └── celery.py         # Celery app instance
├── database/
│   ├── audit.py          # Audit session factory
│   └── models.py         # AuditQueryEvent + AuditIngestionEvent models
├── tasks/
│   └── audit.py          # Background eval + audit write tasks
└── features/
    ├── ingestion/
    │   ├── router.py          # Upload, list, delete endpoints
    │   ├── service.py         # Ingestion pipeline with SSE progress
    │   ├── document_service.py # List, delete, duplicate guard
    │   ├── chunker.py         # Overlap chunking with sentence boundaries
    │   ├── embedder.py        # Batch embedding via Ollama
    │   └── models.py          # Document SQLAlchemy model
    ├── retrieval/
    │   ├── router.py          # Search endpoint
    │   ├── service.py         # Hybrid search orchestration
    │   └── hybrid.py          # Reciprocal Rank Fusion algorithm
    ├── generation/
    │   ├── router.py          # Streaming generation endpoint
    │   ├── service.py         # Prompt builder + Ollama streaming
    │   ├── eval_router.py     # Eval endpoint
    │   └── eval.py            # LLM-as-judge faithfulness + relevance
    └── audit/
        ├── router.py          # Audit query endpoints
        └── service.py         # Audit event retrieval with filters
```

---

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <your-repo>
cd finance-rag
uv sync
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
```

### 2. Pull Ollama models

```bash
ollama pull nomic-embed-text   # embeddings
ollama pull phi4-mini          # generation
ollama pull gemma3:4b          # eval judge
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```env
# PostgreSQL
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password
POSTGRES_DB=rag_finance
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=finance_docs

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=phi4-mini
OLLAMA_EMBED_MODEL=nomic-embed-text
EMBEDDING_SIZE=768
OLLAMA_JUDGE_MODEL=gemma3:4b

# Redis
REDIS_URL=redis://localhost:6379/0

# Authentik
AUTHENTIK_JWKS_URI=http://localhost:9000/application/o/<your-provider>/jwks/
AUTHENTIK_ISSUER=http://localhost:9000/application/o/<your-provider>/
AUTHENTIK_CLIENT_ID=<your-client-id>
AUTHENTIK_CLIENT_SECRET=<your-client-secret>

# App
APP_ENV=development
APP_PORT=8000
```

### 4. Start infrastructure

```bash
docker compose up -d
```

This starts:
- PostgreSQL (port 5432)
- Qdrant (port 6333)
- Redis (port 6379)
- Authentik server (port 9000)
- Authentik worker

Wait ~60 seconds for Authentik to initialize.

### 5. Configure Authentik

Open `http://localhost:9000/if/flow/initial-setup/` and create your admin account.

Then create a Provider:
```
Applications → Providers → Create → OAuth2/OpenID Provider
Name: rag-finance-provider
Client type: Confidential
Copy the Client ID and Client Secret into your .env
```

Then create an Application:
```
Applications → Applications → Create
Name: RAG Finance API
Provider: rag-finance-provider
```

Update `.env` with the JWKS URI from:
```
http://localhost:9000/application/o/rag-finance-provider/.well-known/openid-configuration
```

### 6. Run migrations

```bash
alembic upgrade head
```

This creates:
- `documents` table
- `audit_query_events` table
- `audit_ingestion_events` table

### 7. Start the application

You need **3 terminals** running simultaneously:

**Terminal 1 — API server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Celery worker (background audit jobs):**
```bash
# Linux/Mac
celery -A app.core.celery worker --loglevel=info

# Windows
celery -A app.core.celery worker --loglevel=info --pool=solo
```

**Terminal 3 — Flower (job monitoring UI):**
```bash
celery -A app.core.celery flower --port=5555
```

**Access points:**

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| Authentik Admin | http://localhost:9000/if/admin/ |
| Flower (Celery) | http://localhost:5555 |

---

## Authentication

All API endpoints (except `/health` and `/docs`) require a JWT Bearer token issued by Authentik.

**Get a token:**
```bash
curl -X POST http://localhost:9000/application/o/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
```

**Use the token:**
```bash
curl -X POST http://localhost:8000/api/v1/generation/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"query": "What was Apple net sales in 2024?"}'
```

Tokens expire in 5 minutes by default. Adjust in Authentik provider settings.

**Without a token — all protected routes return:**
```json
{"detail": "Not authenticated"}
```

---

## API Endpoints

All endpoints require `Authorization: Bearer <token>` header except `/health`.

### Ingestion

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/ingestion/upload` | Upload and ingest a PDF (SSE progress) |
| GET | `/api/v1/ingestion/documents` | List all ingested documents |
| DELETE | `/api/v1/ingestion/documents/{file_name}` | Delete a document from both stores |

Upload streams SSE progress events:
```
data: {"status": "extracting", "message": "Extracting text..."}
data: {"status": "chunking", "message": "Created 971 chunks..."}
data: {"status": "embedding", "message": "Embedding 971 chunks...", "total": 971}
data: {"status": "storing", "message": "Storing vectors in Qdrant..."}
data: {"status": "saving", "progress": 500, "total": 971}
data: {"status": "done", "chunks_ingested": 971, "file_name": "apple_10k.pdf"}
```

### Retrieval

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/retrieval/search` | Hybrid search (dense + BM25 + RRF) |

### Generation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/generation/generate` | Stream RAG answer |
| POST | `/api/v1/generation/eval` | Evaluate answer quality |

### Audit

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/audit/queries` | List query audit events |
| GET | `/api/v1/audit/ingestions` | List ingestion audit events |

**Audit filters:**
```
GET /api/v1/audit/queries?client_id=user-123
GET /api/v1/audit/queries?max_faithfulness=0.5   ← find potential hallucinations
GET /api/v1/audit/queries?limit=10&offset=0
GET /api/v1/audit/ingestions?status=error
```

---

## How Hybrid Search Works

Every query runs two searches then merges them with RRF:

**Dense search (Qdrant)** — semantic similarity via cosine distance. Good for conceptual questions.

**Sparse search (PostgreSQL BM25)** — keyword match via `ts_rank`. Good for exact term lookup.

**Reciprocal Rank Fusion:**
```
RRF(chunk) = Σ 1 / (k + rank)
```
Chunks appearing in both lists are naturally boosted. `k=60` is the standard smoothing constant.

---

## Audit System

Every query and ingestion is logged asynchronously via Celery:

```
User request → API responds immediately (streaming)
             ↓ background
             Celery task fires
             → Eval scores computed (gemma3:4b)
             → Audit record written to Postgres
```

**Audit record captures:**
- Who made the request (JWT sub claim from Authentik)
- What was asked / what was ingested
- Retrieved chunks for the query
- Faithfulness score — was the answer grounded in context?
- Relevance score — were the right chunks retrieved?
- Duration in milliseconds
- Timestamp (UTC)

**Find potential hallucinations:**
```bash
GET /api/v1/audit/queries?max_faithfulness=0.5
```

**Direct DB query for auditors:**
```sql
SELECT id, client_id, query, faithfulness_score, relevance_score, created_at
FROM audit_query_events
ORDER BY created_at DESC;
```

---

## Chunking Strategy

- **Chunk size:** 512 characters (~100 words)
- **Overlap:** 64 characters — prevents losing context at boundaries
- **Boundary detection:** walks back to nearest sentence ending before cutting
- **Cleaning:** collapses excessive whitespace and page numbers common in PDFs

---

## Switching Embedding Models

```bash
ollama pull all-minilm
```

Update `.env`:
```env
OLLAMA_EMBED_MODEL=all-minilm
EMBEDDING_SIZE=384
```

Delete the Qdrant collection via dashboard then restart — it recreates automatically.

| Model | Dimensions | Size | CPU Speed |
|---|---|---|---|
| nomic-embed-text | 768 | 274MB | ~2/sec |
| all-minilm | 384 | 46MB | ~10/sec |

---

## Running Tests

```bash
# All tests — auth overridden automatically via tests/conftest.py
pytest tests/ -v

# Specific feature
pytest tests/features/ingestion/ -v
pytest tests/features/retrieval/ -v
pytest tests/features/generation/ -v
pytest tests/features/audit/ -v
```

No running server, Docker, or Ollama needed for tests.

---

## Logs

```
storage/logs/
├── app.log               # current log file
└── app.2024-01-15.log    # previous days (Linux/Mac only)
```

---

## Recommended Financial Datasets

| Source | Description | URL |
|---|---|---|
| SEC EDGAR | 10-K, 10-Q filings for all public companies | https://www.sec.gov/cgi-bin/browse-edgar |
| Apple IR | Apple annual reports in PDF | https://investor.apple.com |
| HuggingFace FinanceQA | 4,000 QA pairs from annual reports | https://huggingface.co/datasets/sweatSmile/FinanceQA |

---

## License

MIT