# 001 — Security & coding principles (carried from the project root)

The user's standing principles, distilled from the root `AGENTS.md`, the
`finance_rag` project conventions, and the user's own direction. They govern every
file in this repo.

## Security

- **No secrets in the repository.** No API keys, tokens, passwords, credentials, or
  `.env`-style files. (The backend work operates under the same rule: secrets live
  only in k8s secrets / local `.env`, never in images or git.)
- The **public** API base URL (`https://finance.tekbridge.co.za`) is the only config
  that may be committed.
- User credentials: entered at runtime, stored only in Keystore-backed storage if at
  all, never logged, never plaintext on disk.
- Any environment-specific value → `BuildConfig` field from a gitignored `local.properties`.

## Coding

- **Truthfulness** — report measured, not claimed. Separate "it works" from "it passed
  the test / returned 200 / rendered on device". Flag real errors plainly.
- **Good enough, not perfect** — fix real errors; flag-and-stop on the last 1%.
  Don't over-polish; don't ship speculative abstractions.
- **Every feature includes tests** — carried from `finance_rag/AGENTS.md`: code without
  tests is unfinished.
- **Root-cause, not symptom** — fix a bug where it originates, once, not at every caller.
- **Minimal & boring** — shortest working diff, fewest files, stdlib/platform first,
  no factory-for-one-product, no config-for-a-value-that-never-changes.
- **Document the why** — every decision gets a note explaining the reasoning, not just the outcome.

## Testing stance (Android)

- JVM unit tests (JUnit) for ViewModels/repositories/parsers — no device, no network.
- Mock the API; never hit the live service or an emulator in CI tests.
- Streaming and auth edge cases (401 → refresh → retry, 429) are the first things to
  test, since they're the risky paths.
