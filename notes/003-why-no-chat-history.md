# Note: why the frontend had no chat histories

**Resolved 2026-10-05.** Built and deployed (API `v0.1.12`, frontend `v0.3.0`); see the bottom of this note and `2026-10-05_09-40.md`.

## Problem statement
books_rag shows a sidebar of past chats that can be reopened on any device. The finance_rag
frontend does not: it shows one conversation, and a list of past questions on the Activity page.

## Why
The finance_rag **API has no concept of a chat**. books_rag has `chats` and `messages` tables and
endpoints to list, open and delete them; finance_rag has none of that.

- `POST /api/v1/generation/generate` takes `{query, top_n}` and nothing else. There is no chat id,
  and earlier turns are not sent, so every question is answered on its own.
- The only server-side record of a question is the **audit trail** (`audit_query_events`): one row
  per question with its answer, retrieved chunks and scores. Rows are not grouped into
  conversations, and nothing links one question to the next.
- Until 2026-10-05 even that was empty in production: no Celery worker was deployed, so audit rows
  were queued and never written, and the worker had a connection-pool bug. Both are fixed
  (see `2026-10-05_09-40.md`).

## What exists today
- **Activity page**: every past question and answer, per user, from the audit trail. Permanent and
  available on any device, but a flat list, not conversations.
- **Current conversation**: kept in the browser's `localStorage` (`frontend/src/components/AskPage.jsx`)
  so a refresh does not lose it. One conversation, this browser only, cleared on log out.

## What real chat histories would take
1. Tables `chats` (id, owner_id, title, created_at) and `chat_messages` (chat_id, role, content,
   sources, created_at), plus an Alembic migration.
2. Endpoints: list / get / delete chats, scoped to the owner like documents are.
3. `generate` accepts an optional `chat_id`, creates a chat when absent, and saves the question and
   the finished answer. The audit task can keep running unchanged.
4. Optionally send the last few turns to the model so follow-up questions work ("and the year
   before?"). This changes the prompt and needs its own check that answers stay grounded.
5. Frontend: a chat list in the sidebar, replacing the `localStorage` conversation.

Steps 1 to 3 and 5 are roughly a day including tests. Step 4 is a separate decision.

## Key decision still open
Whether a chat should carry context between turns (step 4), or just be a saved list of independent
questions. The second is simpler and matches how the API answers today.

## What was built (2026-10-05)
- Steps 1 to 3 and 5 above. Tables `chats` and `chat_messages` (migration `008_create_chats`),
  `GET/GET{id}/DELETE /api/v1/chats`, and `generate` saves the question and the finished answer.
- Assistant messages store the retrieved passages (`sources`, JSONB), so a reopened chat shows the same
  sources without searching again. This also replaced the frontend's second `/retrieval/search` call.
- Chats are private to their owner, admins included. A chat id that isn't yours is a 404.
- A chat's id comes back in the `X-Chat-Id` response header (the answer body is plain streamed text).
- The question is saved after retrieval succeeds, so a rate-limited search leaves no empty chat behind.
- Frontend: chat list in the sidebar grouped by date, each chat at `/chats/<id>`, delete with confirmation.
  The old browser-only conversation (`localStorage`) was removed.
- **Step 4 was first left out, then done the same day** (API `v0.1.13`, frontend `v0.3.1`). See below.

## Follow-up questions (2026-10-05, later)
Sending earlier turns to the model is not enough on its own: retrieval searches with the question text, so
"and services?" finds nothing useful. The latest question is therefore rewritten into a standalone one first.
- `app/features/generation/history.py`: `standalone_query()` (answer model, `storage/prompts/condense.md`, 20 s
  timeout, falls back to the typed question on any failure or an empty/rambling reply) and `format_history()`
  (last 6 messages, `[Source N]` markers removed because they belong to earlier searches, long turns cut).
- `storage/prompts/generation_history.md`: the answer prompt for follow-ups. History is for understanding
  the question and shaping the answer only; every fact must come from the retrieved passages.
- `generate` reads the history BEFORE saving the new question, rewrites, searches with the rewrite, answers.
  A first question skips the rewrite entirely.
- The rewrite is stored on the assistant message (`chat_messages.search_query`, migration 009) and shown in the
  UI as "Searched for: ...", so a misread question is easy to spot.
- **Check answer** now sends `message_id`, and the API scores the saved answer against the passages it was
  built from. Before this, a follow-up was re-searched with its typed words, so the faithfulness score was
  computed against different passages than the answer used. It also needs no embedding call.
- **Audit:** the Activity page still shows what the user typed; relevance is scored against the rewrite
  (`process_query_audit(..., search_query=...)`).
- Checked on the real models: "And services?", "How does that compare with the year before?" and "Make that
  shorter, as one sentence" were all resolved and answered from the passages. Standalone questions in a
  conversation sometimes get the company or year added ("What are the main risk factors?" became "...disclosed
  by Apple in its fiscal 2024 documents"), which is right for a conversation about one company but would narrow
  a search if you switch topics within a chat. Start a new chat for a different company.
