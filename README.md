# Finance RAG API

A production-grade Retrieval-Augmented Generation (RAG) system for financial document analysis. Built with FastAPI, Qdrant, PostgreSQL hybrid search, and Ollama for fully local LLM inference.

---

## What It Does

Upload financial PDFs (SEC 10-K filings, earnings reports) and ask natural language questions. The system retrieves the most relevant chunks using hybrid search and streams a grounded answer — citing exactly which document and chunk it used.

```
PDF Upload → Chunk → Embed → Store (Qdrant + Postgres)
Query → Embed → Hybrid Search (Dense + BM25 + RRF) → Stream Answer
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
| Embedding Model | nomic-embed-text (768 dims) |
| Generation Model | phi4-mini |
| Judge Model | gemma3:4b |
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
│   └── logging.py        # Daily rotating file logger
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
    └── generation/
        ├── router.py          # Streaming generation endpoint
        ├── service.py         # Prompt builder + Ollama streaming
        ├── eval_router.py     # Eval endpoint
        └── eval.py            # LLM-as-judge faithfulness + relevance
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
ollama pull nomic-embed-text
ollama pull phi4-mini
ollama pull gemma3:4b
```

### 3. Configure environment

Copy and edit the environment file:

```bash
cp .env.example .env
```

Key settings:

```env
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password
POSTGRES_DB=rag_finance
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=finance_docs

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=phi4-mini
OLLAMA_EMBED_MODEL=nomic-embed-text
EMBEDDING_SIZE=768
OLLAMA_JUDGE_MODEL=gemma3:4b

APP_ENV=development
APP_PORT=8000
```

### 4. Start infrastructure

```bash
docker compose up -d
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

## API Endpoints

### Ingestion

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/ingestion/upload` | Upload and ingest a PDF |
| GET | `/api/v1/ingestion/documents` | List all ingested documents |
| DELETE | `/api/v1/ingestion/documents/{file_name}` | Delete a document |

Upload streams SSE progress events:
```
data: {"status": "extracting", "message": "Extracting text..."}
data: {"status": "chunking", "message": "Created 42 chunks..."}
data: {"status": "embedding", "message": "Embedding 42 chunks...", "total": 42}
data: {"status": "storing", "message": "Storing vectors in Qdrant..."}
data: {"status": "done", "chunks_ingested": 42, "file_name": "apple_10k.pdf"}
```

### Retrieval

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/retrieval/search` | Hybrid search (dense + BM25 + RRF) |

```json
{
  "query": "What was Apple revenue in Q3?",
  "top_n": 5
}
```

### Generation

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/generation/generate` | Stream RAG answer |
| POST | `/api/v1/generation/eval` | Evaluate answer quality |

---

## How Hybrid Search Works

Every query runs two searches in parallel then merges them:

**Dense search (Qdrant)**
The query is embedded into a 768-dim vector. Qdrant finds the most semantically similar chunks using cosine similarity. Good for conceptual questions.

**Sparse search (PostgreSQL BM25)**
The query is converted to a `tsquery`. PostgreSQL ranks chunks by keyword match frequency using `ts_rank`. Good for exact term lookup.

**Reciprocal Rank Fusion**
Both ranked lists are merged using the RRF formula:

```
RRF(chunk) = Σ 1 / (k + rank)
```

Chunks appearing in both lists are naturally boosted. `k=60` is the standard smoothing constant.

---

## Chunking Strategy

Documents are split into overlapping chunks:

- **Chunk size:** 512 characters (~100 words)
- **Overlap:** 64 characters — prevents losing context at boundaries
- **Boundary detection:** walks back to nearest sentence ending (`.!?`) before cutting
- **Cleaning:** collapses excessive whitespace and page numbers common in PDFs

---

## Evaluation

The `/eval` endpoint uses `gemma3:4b` as an LLM judge to score:

**Faithfulness** — is the answer grounded in the retrieved context?
**Relevance** — did we retrieve chunks that actually relate to the query?

```json
{
  "query": "What was Apple net sales in 2024?",
  "answer": "Apple reported total net sales of 391 billion dollars.",
  "faithfulness": 0.95,
  "relevance": 0.88,
  "chunks_evaluated": 5
}
```

Scores range from 0.0 (bad) to 1.0 (perfect).

---

## Switching Embedding Models

To use a faster/smaller model:

```bash
ollama pull all-minilm
```

Update `.env`:
```env
OLLAMA_EMBED_MODEL=all-minilm
EMBEDDING_SIZE=384
```

Then recreate the Qdrant collection (all vectors must be re-ingested):
```bash
# Delete via dashboard at http://localhost:6333/dashboard
# Then restart server — collection recreates automatically
uvicorn app.main:app --reload --port 8000
```

| Model | Dimensions | Size | CPU Speed |
|---|---|---|---|
| nomic-embed-text | 768 | 274MB | ~2/sec |
| all-minilm | 384 | 46MB | ~10/sec |

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific feature
pytest tests/features/ingestion/ -v
pytest tests/features/retrieval/ -v
pytest tests/features/generation/ -v
```

Tests use mocks for all external dependencies — no running server, Docker, or Ollama needed.

---

## Logs

Daily rotating logs are written to `storage/logs/`:

```
storage/logs/
├── app.log               # current day
├── app.2024-01-15.log    # previous days
└── app.2024-01-14.log
```

30 days of history kept automatically.

---

## Recommended Financial Datasets

| Source | Description | URL |
|---|---|---|
| SEC EDGAR | 10-K, 10-Q filings for all public companies | https://www.sec.gov/cgi-bin/browse-edgar |
| Apple IR | Apple annual reports in PDF | https://investor.apple.com |
| HuggingFace FinanceQA | 4,000 QA pairs from annual reports | https://huggingface.co/datasets/sweatSmile/FinanceQA |

---

## Project Structure

```
finance-rag/
├── .env
├── .gitignore
├── docker-compose.yml
├── pyproject.toml
├── pytest.ini
├── requests.http           # REST Client requests for VSCode
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_ingestion_create_documents_table.py
├── app/
│   ├── main.py
│   ├── core/
│   └── features/
├── tests/
│   └── features/
└── storage/
    ├── logs/
    └── documents/          # Place PDFs here before ingesting
```

---

## License

MIT