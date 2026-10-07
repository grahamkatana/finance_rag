# 005 — Large PDF upload crashed the API

## Goal / problem statement

Uploading the 2024 Berkshire Hathaway annual report (1.8 MB, 546,330 characters) to the live
app killed the API pod. Smaller PDFs worked.

## Diagnosis

Two independent defects, the second hidden behind the first:

1. **Event loop blocked.** `extract_text` (pypdf) and `Chunker.chunk` are synchronous and
   CPU-bound but were called directly inside the async ingestion generator. Extraction took
   about 47 s. During that time `/health` could not answer, three 1 s liveness probes failed,
   and Kubernetes killed the pod (exit 143) between chunking and embedding. Nothing had been
   written to Qdrant or Postgres at that point, so no cleanup was needed.
2. **Qdrant request too large.** Once the pod survived, the single `upsert` of 1,297
   vectors (1536 dimensions) was a 38.4 MB JSON body. Qdrant's limit is 32 MB, so it returned
   400. The router only caught `ValueError`, so the stream just ended and the audit task was
   queued with `status="success"` and 0 chunks.

## Plan and what was done

1. Run `extract_text` and `Chunker.chunk` with `asyncio.to_thread`.
2. Upsert to Qdrant in batches of 200 (`UPSERT_BATCH_SIZE`). If any batch fails, delete the
   vectors already written (they have no Postgres rows, so they would be orphans) and re-raise.
3. Router: catch any other exception, log it, send a generic `error` event to the client and
   audit it with `status="error"`.
4. Manifest `05-app.yaml`: probe `timeoutSeconds: 5`; liveness `failureThreshold: 6`.
5. Tests for each of the above.
6. Build and push `grahamkatana/finance-rag:v0.1.18`, apply the manifest, repeat the upload.

## Files changed

- `app/features/ingestion/service.py` — threads, batched upsert, cleanup on failure.
- `app/features/ingestion/router.py` — generic exception handler, correct audit status.
- `tests/features/ingestion/test_service.py` — extraction/chunking off the loop thread (fails on
  the old code), batching, cleanup on failed upsert.
- `tests/features/ingestion/test_router.py` — unexpected error is streamed and audited as an error.
- `~/Desktop/kbctl/finance-rag-k8s/05-app.yaml` — probes; tag v0.1.18 (three places).

## Verification

- `uv run pytest tests/ -q --timeout=30`: 347 passed.
- Live upload of the same PDF on v0.1.18: 1,297 chunks stored in about 55 s; a question about
  share repurchases returned a cited answer.

## Key decisions

- Threads, not a process pool or a faster PDF library. The pod has a 512 Mi limit and a
  500 m CPU limit, a pool would double memory, and PyMuPDF is AGPL.
- Looser probes as well as the code fix, so a busy single-replica API is not killed for being
  slow. Trade-off: a truly hung pod now takes about 2 minutes to restart.

## Open items

- One `/health` call still timed out at 10 s during the chunking step and the readiness probe
  failed once (the pod is briefly removed from the Service, not restarted). Chunking is pure
  Python and holds the GIL. Fix if it matters: move extraction and chunking to the Celery
  worker container, which already exists.
- No upload size limit is enforced in the API or the ingress; a much larger PDF will take
  proportionally longer.
