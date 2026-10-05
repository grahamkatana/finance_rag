# AGENTS.md — finance_rag/android (native Android client)

Instructions for AI agents working in this repo. Read this before writing code.

## Project

Native Android client (Kotlin + Jetpack Compose) for the `finance_rag` API at
`https://finance.tekbridge.co.za`. A chat client: the user logs in, asks questions
about their financial documents, and reads streamed, source-grounded answers.

The backend does retrieval/LLM/audit. This app does auth + ask + render the stream.

## Non-negotiables

### 1. No secrets in code — ever
- The **only** thing allowed to be hardcoded is the public API base URL.
- No API keys, no tokens, no passwords, no credentials, no committed `.env`-style files.
- User credentials are entered at runtime and stored securely (Keystore-backed), never logged, never plaintext on disk.
- Environment-specific values go in `BuildConfig` fields populated from a gitignored `local.properties`, never committed.
- Full stance: `notes/001-security-and-coding-principles.md`.

### 2. Every feature includes tests — or it isn't finished
- A ViewModel/repository with logic and no unit test is unfinished work.
- Tests mock the network and API. No test hits the live API, needs an emulator, or does real I/O.
- `./gradlew test` passes with no device.

### 3. Truthfulness — separate reported from measured
- "It works" must say *how it was verified* (device, emulator, curl, log line).
- Flag real errors plainly. A swallowed 401 or a silently failed stream is a bug, not a "graceful" outcome.

### 4. Good enough, not perfect
- Ship the smallest thing that proves the point. No speculative abstractions, no "for later" layers.
- Flag-and-stop on the last 1% rather than over-polishing.

### 5. Build in stages
- Never one big-bang scaffold. Vertical slice first, expand stage by stage.
- Rationale + stage plan: `notes/000-how-and-why.md`.

## Process

### Notes (`notes/`)
- Worklog: `notes/yyyy-mm-dd_HH-MM.md` — one per session (summary, files changed, status, next steps).
- Decision notes: `notes/NNN-short-description.md` — goal, plan, and the **why** behind each decision.
- The "why" is mandatory. Code without a recorded reason is debt.

## Conventions

- Kotlin, Jetpack Compose, Material 3, minSdk 26.
- Library choices (HTTP client, DI, persistence) are decided in `notes/` as each stage lands —
  do not add a dependency without recording why it was picked.
- Architecture stays minimal until a stage earns more (see rule 4).

## Definition of done (a stage is complete when)
- [ ] The feature works and was verified on a device/emulator against the live API (or a mocked contract test).
- [ ] Tests are written and `./gradlew test` passes.
- [ ] A note records what was done and why.
- [ ] A worklog entry exists for the session.
