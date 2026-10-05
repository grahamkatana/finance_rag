# 000 — How & why: native Android, staged scaffold

## The decision: native Android (Kotlin + Jetpack Compose)

Chosen over Flutter and React Native.

**Why:**
- A deliberate **learning opportunity** — native Kotlin, Compose, and the Android SDK
  itself, not a cross-platform abstraction over them.
- Scope is **Android-only** right now (no iOS requirement), so Flutter's single-codebase
  advantage doesn't apply, and native's advantage (full SDK access, best Android feel,
  smaller app) is real.
- The app is HTTP + streaming + text UI, so it exercises exactly the parts of Android
  worth learning: lifecycle, coroutines/Flow, networking, token storage.

Trade-off accepted: no iOS path without a second codebase later. If iOS ever becomes
real, retrieval/LLM logic is all backend-side, so a client rewrite is mostly UI — acceptable.

## How we build: staged, vertical slice first

We do **not** scaffold everything at once. Stages:

1. **Vertical slice** — login → ask one question → stream the answer into a bubble.
   Two screens, minimal. Proves auth, token refresh, streaming, error/rate-limit
   handling, and the live API contract before any real UI investment.
2. **Citations** — tap an answer to see source chunks (uses `/retrieval/search`).
3. **Polish** — message history, loading/error states, theming.
4. **Extras** — search-only mode, thread history, upload/audit (admin) — only if wanted.

**Why staged:** each stage is a small, verifiable increment; the risky unknowns
(streaming, auth edge cases) get resolved in stage 1 when they're cheap to change.

## Architecture (minimal, growing with need)

- `ui/` — Compose screens (login, chat).
- `data/` — API client, token store, repositories.
- No `domain/` layer until a stage demonstrates the need (no speculative layers).

## Open questions (decide in the notes when each stage lands)
- HTTP client: Retrofit+OkHttp vs Ktor (streaming matters for `/generate`).
- Token persistence: Keystore-backed encrypted storage vs DataStore.
- DI: manual vs Hilt.
