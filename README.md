# Finance RAG API

A production-grade Retrieval-Augmented Generation system for financial document analysis. Built with FastAPI, Qdrant, PostgreSQL hybrid search, a multi-provider LLM connector, Authentik for authentication, and Celery for background audit processing.

---

## What It Does

Upload financial PDFs and ask natural language questions. The system retrieves the most relevant chunks using hybrid search, streams a grounded answer citing the exact source document and chunk, and logs every interaction for audit and compliance purposes.

The ingestion pipeline extracts text from PDFs, splits it into overlapping chunks, embeds each chunk into a vector, and writes both the vectors and metadata to dual stores — Qdrant for semantic search and PostgreSQL for keyword search. At query time both stores are searched in parallel and the results are merged using Reciprocal Rank Fusion before being passed to the language model.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn |
| Vector store | Qdrant |
| Relational store | PostgreSQL with tsvector full-text search |
| ORM | SQLAlchemy async |
| Migrations | Alembic |
| LLM connector | Multi-provider: Ollama, OpenAI, Groq, DeepSeek, Grok, Gemini, Mistral, Voyage AI |
| Auth | Authentik, OAuth2, JWT |
| Background jobs | Celery, Redis |
| Job monitoring | Flower |
| Dependency management | uv |
| Testing | pytest, pytest-asyncio |
| Frontend | React, Vite, TypeScript |

---

## Architecture

```
app/
├── core/
│   ├── config.py          Settings via pydantic-settings
│   ├── database.py        Async SQLAlchemy engine and session
│   ├── qdrant.py          Qdrant client and collection initialisation
│   ├── logging.py         Rotating file logger
│   ├── auth.py            JWT validation via Authentik JWKS
│   ├── celery.py          Celery application instance
│   └── llm/
│       ├── base.py        Abstract interfaces for LLM and embedder
│       ├── connector.py   Single entry point for all providers
│       └── providers/
│           ├── ollama.py  Local inference
│           ├── openai.py  OpenAI, Groq, DeepSeek, Grok
│           ├── gemini.py  Google Gemini
│           ├── mistral.py Mistral AI
│           └── voyage.py  Voyage AI embeddings
├── core/prompts/
│   └── loader.py          Reads prompt templates from storage/prompts/
├── database/
│   ├── audit.py           Audit session factory
│   └── models.py          Audit event models
├── tasks/
│   └── audit.py           Background eval and audit write tasks
└── features/
    ├── ingestion/          Upload, chunk, embed, store
    ├── retrieval/          Hybrid search with RRF fusion
    ├── generation/         Prompt building, streaming, eval
    └── audit/              Audit trail query endpoints

storage/
└── prompts/
    ├── generation.md           RAG answer prompt template
    ├── generation_no_context.md Fallback when no chunks retrieved
    ├── faithfulness.md          Eval faithfulness judge prompt
    └── relevance.md             Eval relevance judge prompt
```

Prompts live in `storage/prompts/` as Markdown files with `{variable}` placeholders. Changing a prompt requires no code change and no restart — edit the file and the next request picks up the new template.

---

## Prerequisites

- Python 3.11 or later
- uv package manager
- Docker and Docker Compose
- Ollama (for local inference)

---

## Installation

```bash
git clone <your-repo>
cd finance-rag
uv sync
source .venv/bin/activate
```

Pull the Ollama models used by default:

```bash
ollama pull nomic-embed-text
ollama pull phi4-mini
ollama pull gemma3:4b
```

---

## Configuration

Copy `.env.example` to `.env`. The default configuration uses OpenAI for generation and embeddings:

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

# Generation — OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_BASE_URL=
LLM_API_KEY=sk-your-openai-key

# Embeddings — OpenAI
EMBED_PROVIDER=openai
EMBED_MODEL=text-embedding-3-small
EMBED_BASE_URL=
EMBED_API_KEY=sk-your-openai-key
EMBEDDING_SIZE=1536

# Eval judge — Ollama (local, free)
JUDGE_PROVIDER=ollama
JUDGE_MODEL=gemma3:4b
JUDGE_BASE_URL=http://localhost:11434
JUDGE_API_KEY=

# Redis
REDIS_URL=redis://localhost:6379/0

# Authentik
AUTHENTIK_JWKS_URI=http://localhost:9000/application/o/rag-finance-provider/jwks/
AUTHENTIK_ISSUER=http://localhost:9000/application/o/rag-finance-provider/
AUTHENTIK_CLIENT_ID=your-client-id
AUTHENTIK_CLIENT_SECRET=your-client-secret

# App
APP_ENV=development
APP_PORT=8000
```

### Switching providers

The connector reads `LLM_PROVIDER`, `EMBED_PROVIDER`, and `JUDGE_PROVIDER` at startup. To switch, update the relevant variables and restart the server.

OpenAI-compatible providers share the same file and differ only by `base_url`:

```env
# Groq — fastest inference
LLM_PROVIDER=openai
LLM_MODEL=llama-3.3-70b-versatile
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk-your-groq-key

# DeepSeek — cheapest generation
LLM_PROVIDER=openai
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-your-deepseek-key

# Grok — xAI
LLM_PROVIDER=openai
LLM_MODEL=grok-4
LLM_BASE_URL=https://api.x.ai/v1
LLM_API_KEY=xai-your-key

# Fully local
LLM_PROVIDER=ollama
LLM_MODEL=phi4-mini
LLM_BASE_URL=http://localhost:11434
LLM_API_KEY=
```

Embedding providers have their own setting. Note that switching the embedding model requires re-ingesting all documents because vector dimensions must match the Qdrant collection configuration.

```env
# Voyage AI — best retrieval quality for finance and legal
EMBED_PROVIDER=voyage
EMBED_MODEL=voyage-finance-2
EMBED_API_KEY=pa-your-voyage-key
EMBEDDING_SIZE=1024

# Gemini — cheapest embeddings at $0.006 per million tokens
EMBED_PROVIDER=gemini
EMBED_MODEL=models/text-embedding-005
EMBED_API_KEY=AIza-your-gemini-key
EMBEDDING_SIZE=768

# Mistral — EU servers, GDPR compliant
EMBED_PROVIDER=mistral
EMBED_MODEL=mistral-embed
EMBED_API_KEY=your-mistral-key
EMBEDDING_SIZE=1024
```

---

## Running the Application

Start the infrastructure:

```bash
docker compose up -d
```

Run migrations:

```bash
alembic upgrade head
```

You need three terminals running simultaneously.

**Terminal 1 — API server:**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Celery worker:**
```bash
# Linux / Mac
celery -A app.core.celery worker --loglevel=info

# Windows
celery -A app.core.celery worker --loglevel=info --pool=solo
```

**Terminal 3 — Flower job monitor:**
```bash
celery -A app.core.celery flower --port=5555
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API documentation | http://localhost:8000/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Authentik admin | http://localhost:9000/if/admin/ |
| Flower | http://localhost:5555 |

---

## Authentication

All endpoints except `/health` require a valid JWT Bearer token issued by Authentik.

Configure Authentik by creating an OAuth2/OpenID provider named `rag-finance-provider` with client type Confidential, then creating an application linked to that provider. Add `http://localhost:5173/callback` as a redirect URI for the React frontend.

Obtain a token for API testing:

```bash
curl -X POST http://localhost:9000/application/o/token/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=YOUR_CLIENT_ID&client_secret=YOUR_CLIENT_SECRET"
```

Use the token on protected requests:

```bash
curl -X POST http://localhost:8000/api/v1/generation/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"query": "What was Apple total net sales in 2024?"}'
```

---

## API Reference

All endpoints require an `Authorization: Bearer <token>` header.

### Ingestion

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/ingestion/upload` | Upload a PDF. Streams SSE progress events. |
| GET | `/api/v1/ingestion/documents` | List all ingested documents. |
| DELETE | `/api/v1/ingestion/documents/{file_name}` | Delete a document from both Qdrant and PostgreSQL. |

### Retrieval

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/retrieval/search` | Run hybrid search and return ranked chunks. |

### Generation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/generation/generate` | Stream a grounded answer to a query. |
| POST | `/api/v1/generation/eval` | Score an answer for faithfulness and relevance. |

### Audit

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/audit/queries` | List query audit events with optional filters. |
| GET | `/api/v1/audit/ingestions` | List ingestion audit events. |

Useful audit filters:

```
GET /api/v1/audit/queries?max_faithfulness=0.5
GET /api/v1/audit/queries?client_id=user-id
GET /api/v1/audit/ingestions?status=error
```

---

## How Hybrid Search Works

At query time the system runs two searches and merges the results.

Dense search queries Qdrant using the embedded query vector and cosine similarity. This captures semantic meaning and handles paraphrasing well.

Sparse search queries PostgreSQL using `plainto_tsquery` and `ts_rank`. This matches exact keywords and handles numeric identifiers, ticker symbols, and specific terminology reliably.

The two ranked lists are merged with Reciprocal Rank Fusion:

```
RRF score = sum of (1 / (k + rank)) across all lists
```

where `k = 60` is the standard smoothing constant. Documents appearing in both lists receive contributions from each, naturally boosting results that are both semantically relevant and keyword-matched.

---

## Audit System

Every query and ingestion is recorded asynchronously via Celery so the user experience is not affected.

After a generate request completes, a Celery task runs the eval judge against the answer and the retrieved chunks, then writes a record to `audit_query_events` containing:

- User identity from the JWT subject claim
- The query and the generated answer
- The retrieved chunks
- Faithfulness score: was the answer grounded in the context
- Relevance score: did the retrieved chunks relate to the query
- Total duration in milliseconds
- Timestamp in UTC

To find potential hallucinations:

```sql
SELECT id, client_id, query, faithfulness_score, created_at
FROM audit_query_events
WHERE faithfulness_score < 0.5
ORDER BY created_at DESC;
```

---

## Prompt Management

Prompt templates live in `storage/prompts/` as plain Markdown files. The loader reads them on first use and caches them in memory.

To update a prompt, edit the relevant file. The change takes effect on the next server restart. To reload without restarting, call `load_prompt.cache_clear()` in a Python shell.

Variable substitution uses Python string formatting with named placeholders: `{query}`, `{context}`, `{answer}`.

---

## Testing

```bash
# Full suite
pytest tests/ -v

# With timeout to catch hanging tests
pytest tests/ -v --timeout=10

# Specific feature
pytest tests/features/ingestion/ -v
pytest tests/core/llm/ -v
```

No running server, database, or model inference is needed for tests. All external dependencies are mocked. Celery tasks are patched in `tests/conftest.py` to prevent Redis connection attempts.

---

## Recommended Datasets

| Source | Description |
|---|---|
| SEC EDGAR | 10-K and 10-Q filings for all US public companies |
| Apple Investor Relations | Annual reports in PDF |
| HuggingFace FinanceQA | Question-answer pairs from annual reports for eval |

---

## License

MIT