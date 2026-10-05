# Plan: Web frontend

## Goal
Give the API a browser UI, in the same style as the books_rag frontends
(Vite + React + Tailwind v4, shadcn-style components), covering every flow
the API already exposes.

## Steps
1. Scaffold `frontend/` from the books_rag UI primitives (Button, Dialog, Table, colour tokens).
2. API client: login, access-token refresh on 401, plain-text answer stream, SSE upload progress.
3. Pages: Ask, Documents (upload / share / delete), Activity (questions + uploads), Add user (admins).
4. Backend: return the grantee's email from `list_shares`, since unsharing is by email.
5. Image + k8s manifests (not deployed).

## Files changed
- `frontend/` — new app (see worklog for the breakdown).
- `app/features/ingestion/document_service.py` — `list_shares` joins `users` to return `email`.
- `tests/features/ingestion/test_document_service.py` — new test for the above.
- `.dockerignore` — keeps `frontend/` out of the API image.
- `README.md` — "Web Frontend" section.

## Key decisions
- **One app, not three.** books_rag splits chat / admin / verify; here everything is per-user
  behind the same login, so one sidebar app is enough. "Add user" only shows for admins.
- **Sources come from a parallel `/retrieval/search`.** `/generation/generate` streams plain text
  and does not return its chunks. The same query + `top_n` gives the same ranked chunks the model
  saw as "Source 1..N". Costs one extra retrieval per question; returning the chunks from the
  generate stream itself would remove it but changes the API the Android client uses.
- **Answers render as markdown without raw HTML** (no `rehype-raw`), plus a strict CSP in nginx.
- **No chat history across reloads.** The API has no conversation model; past questions and
  answers are on the Activity page via the audit endpoints.
- **Same host as the API.** The ingress keeps `/api`, `/docs`, `/openapi.json`, `/health` on the
  API and sends everything else to the frontend, so existing clients are unaffected.
