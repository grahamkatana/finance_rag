# Usage and cost dashboard (admin) — 7 October 2026

**What it does.** Every model call is counted (tokens in and out) in `usage_events`: chat answers, the question rewriter, the judge, and embeddings. Admins get **Usage & cost** in the sidebar: month to date, a projection to month end, cost per day, per-model table, provider balances, and editable prices.

**Where.** `app/features/usage/` (recorder, service, balances, router at `/api/v1/admin/usage/*`), migration `011`, hooks in `core/llm/providers/openai.py` and `ollama.py`, page `frontend/src/components/UsagePage.jsx`.

**What is real and what is estimated.**
- Token counts come from the provider's own usage figures. If a provider reports none, four characters per token is used and the row is marked estimated (`~` in the table).
- Cost = tokens x the price you set. Only `text-embedding-3-small` is seeded ($0.02 per million). Every other price must be entered from the provider's pricing page; models with no price show "no price" and count as $0 in totals. Ollama Cloud is plan-based, so $0 per token is the honest price there.
- **Balances.** DeepSeek has a real balance endpoint (`GET /user/balance`), used when `DEEPSEEK_API_KEY` is set. OpenAI has no credit-balance API: with `OPENAI_ADMIN_KEY` set the page shows month-to-date spend from the Costs API, not credit left. Ollama and Gemini have nothing. For those, enter your top-up as "credit left" and the page subtracts priced usage since.
- Finance does not use DeepSeek today, so set `DEEPSEEK_API_KEY` only if it ever does.

**Not done / limits.** Usage is not split per user yet. Voyage, Gemini and Mistral providers are not instrumented (not used in production). Not deployed at the time of writing: needs migration 011 and an image build.

**Tested.** `tests/features/usage/test_usage.py` (cost, projection, balance parsing, admin-only, recorder never raises, embedder records); the migration and the summary SQL were also run against a throwaway Postgres 16. Full suite 357 passed.
