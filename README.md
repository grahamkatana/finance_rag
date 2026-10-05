# Finance RAG API

A production-grade Retrieval-Augmented Generation system for financial document analysis. Built with FastAPI, Qdrant, PostgreSQL hybrid search, a multi-provider LLM connector, local JWT authentication, and Celery for background audit processing.

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
| Auth | Local JWT (HS256), per-user data scoping |
| Background jobs | Celery, Redis |
| Dependency management | uv |
| Testing | pytest, pytest-asyncio |

---

## Architecture

```
app/
├── core/
│   ├── config.py          Settings via pydantic-settings
│   ├── database.py        Async SQLAlchemy engine and session
│   ├── qdrant.py          Qdrant client and collection initialisation
│   ├── logging.py         Rotating file logger
│   ├── auth.py            JWT validation (local HS256) + admin guard
│   ├── rate_limit.py      Redis-backed rate limiting
│   ├── celery.py          Celery application instance
│   └── llm/
│       ├── base.py        Abstract interfaces for LLM and embedder
│       ├── connector.py   Single entry point for all providers
│       └── providers/
│           ├── ollama.py  Ollama (local or cloud)
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
- Ollama (only for fully-local inference; cloud providers need no local install)

---

## Installation

```bash
git clone <your-repo>
cd finance-rag
uv sync
source .venv/bin/activate
```

To run fully local (no cloud API keys), pull the Ollama models:

```bash
ollama pull nomic-embed-text
ollama pull phi4-mini
ollama pull gemma3:4b
```

---

## Configuration

Copy `.env.example` to `.env`. The default configuration uses Ollama Cloud for generation and Voyage AI for embeddings:

```env
# PostgreSQL
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=rag_finance
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Qdrant
QDRANT_HOST=domain.com
QDRANT_PORT=443
QDRANT_COLLECTION=finance_docs
QDRANT_API_KEY=CHANGE_ME

# Generation — Ollama Cloud
LLM_PROVIDER=ollama
LLM_MODEL=gemma4:31b
LLM_BASE_URL=https://ollama.com
LLM_API_KEY=CHANGE_ME

# Embeddings — Voyage AI
EMBED_PROVIDER=voyage
EMBED_MODEL=voyage-finance-2
EMBED_BASE_URL=
EMBED_API_KEY=CHANGE_ME
EMBEDDING_SIZE=1024

# Judge — Ollama Cloud (larger model)
JUDGE_PROVIDER=ollama
JUDGE_MODEL=deepseek-v4-pro:0813
JUDGE_BASE_URL=https://ollama.com
JUDGE_API_KEY=CHANGE_ME

# Redis
REDIS_URL=redis://redis:6379/0

# JWT auth
JWT_SECRET=CHANGE_ME
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin seed (created on first startup)
ADMIN_EMAIL=admin@example.com
ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE_ME

# Rate limiting (requests per 60s window; optional — defaults shown)
RATE_LIMIT_LOGIN_PER_MINUTE=10
RATE_LIMIT_GENERATE_PER_MINUTE=10
RATE_LIMIT_EVAL_PER_MINUTE=10

# App
APP_ENV=production
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

You need two terminals running simultaneously.

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

**Optional — Flower job monitor** (inspect Celery task state):

```bash
celery -A app.core.celery flower --port=5555
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API documentation | http://localhost:8000/docs |
| Qdrant dashboard | http://localhost:6333/dashboard |
| Flower (optional) | http://localhost:5555 |

---

## Web Frontend

A browser UI lives in `frontend/` (Vite + React + Tailwind): ask questions with streamed answers
and their source passages, upload / share / delete PDFs, and review past questions and uploads.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5176, proxies /api to the API on :8000
npm test         # stream/SSE parsing checks
```

For production it builds to a static nginx image (`frontend/Dockerfile`) that proxies `/api/`
to the API. Accounts are created by an admin ("Add user" in the sidebar); there is no sign-up.

## Restoring history from before chats existed

Questions asked before chats were added are in the audit trail only. To show them in a user's chat list:

```bash
kubectl -n finance-rag exec deploy/finance-rag -c finance-rag -- \
  uv run python -m app.backfill_chats --username <name> --dry-run   # count only
kubectl -n finance-rag exec deploy/finance-rag -c finance-rag -- \
  uv run python -m app.backfill_chats --username <name>
```

One chat per question, with its answer, sources and original time. Safe to re-run. To undo, delete the chats in the sidebar.

## Authentication

Authentication is a **local JWT implementation** — no external identity provider. Users are stored in the `users` table (PostgreSQL) with bcrypt-hashed passwords, and tokens are signed with HS256 using `JWT_SECRET`.

- **Public self-registration is disabled** — `POST /auth/register` always returns `403`.
- **Admin account** is seeded on first startup from `ADMIN_EMAIL` / `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
- **Only admins create users** — `POST /auth/admin/users` requires an admin token.
- **Per-user data scoping** — documents, retrieval, and generation are filtered by the authenticated user; admins see everything.

Log in to obtain a token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "YOUR_PASSWORD"}'
```

The response contains `access_token` (30 min) and `refresh_token` (7 days). Use the access token on protected requests:

```bash
curl -X POST http://localhost:8000/api/v1/generation/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"query": "What was Apple total net sales in 2024?"}'
```

### Rate limiting

`/auth/login`, `/generation/generate`, and `/generation/eval` are rate-limited (default 10 requests per minute, keyed by client IP for login and by user for the others). Tune via `RATE_LIMIT_*_PER_MINUTE`. Exceeding the limit returns `429` with a `Retry-After` header.

---

## API Reference

All data endpoints require an `Authorization: Bearer <token>` header. `login` and `refresh` are the only public routes.

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Disabled — always returns `403`. |
| POST | `/api/v1/auth/login` | Exchange username/password for access + refresh tokens. |
| POST | `/api/v1/auth/refresh` | Exchange a refresh token for new tokens. |
| GET | `/api/v1/auth/me` | Return the current user. |
| POST | `/api/v1/auth/admin/users` | Create a user (admin only). |
| GET | `/api/v1/auth/admin/users` | List all users (admin only). |
| PATCH | `/api/v1/auth/admin/users/{id}` | Grant or revoke admin access (admin only). |

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
| POST | `/api/v1/generation/generate` | Stream a grounded answer to a query. Optional `chat_id` continues a chat; the chat's id is returned in the `X-Chat-Id` header. |
| POST | `/api/v1/generation/eval` | Score an answer for faithfulness and relevance. With `message_id` (a saved answer in your chats) it is scored against the passages that answer used, with no new search. |

### Chats

Every question asked through `generate` is saved in a chat, together with its answer and the passages the
answer was built from. Chats are private to their owner (admins included); the admin view of everyone's
questions is the audit trail below.

**Follow-up questions.** When `chat_id` is given, the last six messages of that chat are used in two ways.
The latest question is first rewritten by the answer model into a standalone one ("and services?" becomes
"What were Apple's services net sales in fiscal 2024?"), and that rewrite is what gets searched, so retrieval
works for follow-ups. The same messages are then included in the answer prompt so requests about the answer
itself ("shorter", "as a table") work; facts still come only from the retrieved passages. A first question
costs nothing extra; a follow-up adds one short model call, and falls back to the question as typed if it fails.
The rewrite is saved with the answer (`search_query` on each message). Prompts: `storage/prompts/condense.md`
and `generation_history.md`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/chats` | List your chats, most recently active first. |
| GET | `/api/v1/chats/{id}` | A chat with its messages; assistant messages carry their `sources`. |
| DELETE | `/api/v1/chats/{id}` | Delete a chat and its messages. |

### Android app releases

Every version of the Android app is stored (in PostgreSQL, so it is backed up with the rest) and can be
downloaded again. The web app shows them on its **Android app** page; admins publish and delete versions.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/releases` | All versions, newest first, with size and SHA-256. |
| POST | `/api/v1/releases` | Publish a version (admin). Multipart: `file`, `version_name`, `version_code`, `notes`. |
| POST | `/api/v1/releases/{id}/download-url` | A link to the file, valid for 2 minutes. |
| GET | `/api/v1/releases/{id}/file?t=...` | The APK, as an attachment. The token replaces the login header, which a plain browser link cannot send. |
| DELETE | `/api/v1/releases/{id}` | Delete a version (admin). |

A version code must be higher than every earlier one (Android uses it to decide what is newer). Uploads are limited
to 50 MB and must be a zip containing `AndroidManifest.xml` and compiled code. The download token has its own type, so
it opens nothing else in the API and a login token does not open the file.

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

No running server, database, or model inference is needed for tests. All external dependencies are mocked. Celery tasks and the rate limiter's Redis client are patched in `tests/conftest.py` to prevent connection attempts.

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
