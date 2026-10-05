> **Status (2026-10-05):** stages 1 and 2 are built, and the framework question in §2 was settled in favour of native Android (`notes/000`). The API has grown since this plan was written; see `notes/002`. What has and has not been verified is in `notes/003`.

# finance-rag Mobile — Scoping Plan

A mobile client for the live `finance_rag` API (https://finance.tekbridge.co.za).
This doc scopes the work and defines the **vertical slice** we build first. It does
**not** commit to a framework yet — that decision is still open (see §2).

---

## 1. What the app is

A native chat client for the RAG backend. A user logs in, asks a natural-language
question about their uploaded financial documents, and reads a grounded answer that
is streamed back token-by-token with citations to the source chunks.

The backend already does all the hard parts (hybrid search, LLM grounding, audit
logging). The app's only job is: **auth + send a question + render a streamed answer**.

## 2. The one blocking decision: Flutter vs native Android

Original ask was "native Android, not Flutter / React Native" — but that's now being
reconsidered. This is the only thing that must be settled before code, because it
changes the entire scaffold.

| | Native Android (Kotlin + Jetpack Compose) | Flutter (Dart) |
|---|---|---|
| Platforms | Android only | Android + iOS from one codebase |
| Feel / SDK access | Best Android-native, full SDK | Great, but a Dart layer over platform |
| Iteration | Slower builds, Compose preview | Hot reload |
| App size / runtime | Smaller | Larger (Dart VM) |
| Cost of "I want iOS later" | Rewrite in another framework | $0 — already covered |

**The real question is "is iOS in scope?"** — not a technical one.

- **Android-only, forever** → native Kotlin + Compose (matches the original ask).
- **iOS matters now or maybe later** → Flutter (one codebase, and this app is pure
  HTTP + text streaming, which Flutter handles trivially).

Recommendation if iOS is even *maybe*: Flutter. The app has no device-hardware
surface (no camera/BLE/NFC) — it's API + UI, exactly where Flutter's single-codebase
win is cheapest and native's advantage is thinnest.

## 3. Vertical slice (build this first, in whichever framework)

One end-to-end journey, minimal UI, runnable against the live API. This is the
de-risking step: it proves the API contract, auth, and streaming before we commit to
the full UI.

**Journey:** enter credentials → `POST /auth/login` → keep JWT → type one question →
`POST /generation/generate` with `Authorization: Bearer <token>` → stream `text/plain`
tokens into a chat bubble → handle a bad login and a rate-limit.

**Two screens, nothing more:**
1. **Login** — username/password, show a clear error on 401.
2. **Chat** — one text field + one message list that appends tokens as they arrive.

**Exit criteria (the slice is "done" when):**
- [ ] Login succeeds against live API and stores `access_token` + `refresh_token`.
- [ ] A question streams its answer live into the UI (not after-the-fact).
- [ ] A 401 mid-session triggers a silent `POST /auth/refresh` + retry.
- [ ] A 429 (rate limit) shows a friendly "slow down" message, no crash.
- [ ] App works on a physical Android device against `https://finance.tekbridge.co.za`.

## 4. API contract (what the slice consumes)

Base URL: `https://finance.tekbridge.co.za`

| Endpoint | Method | Body | Response |
|---|---|---|---|
| `/api/v1/auth/login` | POST | `{username, password}` | `{access_token, refresh_token}` (JWT HS256) |
| `/api/v1/auth/refresh` | POST | `{refresh_token}` | new token pair |
| `/api/v1/auth/me` | GET | — | current user |
| `/api/v1/generation/generate` | POST | `{query, top_n}` | **`text/plain` token stream** (Bearer JWT) |
| `/api/v1/retrieval/search` | POST | `{query, top_n}` | `{results:[{chunk_text, file_name, chunk_index, source, score}]}` |

Notes:
- **Registration is disabled** (`POST /auth/register` → 403). Users are created by an
  admin (`POST /auth/admin/users`). The app ships a **login-only** flow; account
  creation is out of scope for the client.
- **`/generate` streams raw `text/plain`**, not SSE and not JSON — a plain streaming
  HTTP read (OkHttp `ResponseBody` / Dart `http.StreamedResponse`). Simpler than SSE.
- Rate limits exist on `/login` and `/generate` (429) — the slice must handle 429.

## 5. Known risks to de-risk in the slice

1. **Streaming is the tricky part** — token-by-token append to a list without jank.
   (Straightforward raw-HTTP stream either way.)
2. **JWT expiry mid-answer** — refresh-and-retry logic, not a dead stream.
3. **Rate limiting** — 429 must not look like a crash.
4. **HTTPS cert** — the live host has a valid cert, so no special trust config needed.

## 6. After the slice (roadmap, not yet scoped in detail)

1. Citations — tap an answer to see the retrieved `chunk_text`/`file_name` sources
   (call `/retrieval/search` alongside, or parse citation metadata from the answer).
2. Search-only mode (browse matches without generating).
3. Chat history / threads (client-side or a backend extension).
4. Document upload (`/ingestion`) and audit history (`/audit`) — likely admin-only.
5. Push notifications, offline drafts — later, if ever.

## 7. Next step (needs your decision)

Pick the framework (§2). On that answer I'll scaffold the vertical slice — buildable,
two screens, streaming against the live API — and we validate it on a device before
building out the real UI.
