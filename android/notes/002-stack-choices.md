# 002 — Stack choices (and the API as it is now)

Each dependency has a reason. `AGENTS.md` requires that reason to be written down here.

## Dependencies

| Choice | Over | Why |
|---|---|---|
| **OkHttp** | Retrofit, Ktor | Five calls do not need an annotation layer. The one hard call, `/generate`, is a plain streamed `text/plain` body, and OkHttp exposes the raw stream. `MockWebServer` (same project) makes the auth and streaming tests honest: they run against a real HTTP server, not mocks of our own code. |
| **kotlinx.serialization** | Moshi, Gson, `org.json` | Kotlin-native, no reflection, and works in plain JVM unit tests (`org.json` is only a stub there). |
| **Own AES-GCM + Android Keystore** | `EncryptedSharedPreferences`, DataStore | Jetpack's security-crypto library is deprecated. The Keystore code is about 40 lines and the key never leaves the keystore. DataStore would store tokens in plaintext. |
| **Plain Compose + Material 3**, state held in a `ViewModel` | Navigation library, Hilt | Two screens. A boolean (`loggedIn`) is the navigation; `AppContainer`-style wiring is the `Application` class. Add a navigation library when there is a third screen worth navigating to. |
| **A small markdown parser (~100 lines)** | A markdown library | Answers use only headings, lists, tables, bold, italic and code. A library brings images and links the app does not need, and a pure-Kotlin parser is unit testable. |
| **Material icons core only** | `material-icons-extended` | The extended set adds several MB for three icons. |
| **minSdk 26 / target 35** | | Android 8.0+ is 97%+ of devices and gives adaptive icons without PNG fallbacks. |

## The API has moved on since PLAN.md

`PLAN.md` was written when the API had only login, generate and search. The app uses what exists now:

- `POST /generation/generate` takes an optional `chat_id` and returns the chat's id in the
  **`X-Chat-Id` response header**. The body is still plain streamed text.
- `GET /chats` and `GET /chats/{id}` give saved chats; each assistant message carries its
  `sources` (the passages it used) and, for a follow-up, `search_query` (what it was rewritten to).
  So sources come from the saved chat after the answer ends, with no second search.
- Follow-up questions are handled by the API (it rewrites them and uses recent messages). The app
  only sends the same `chat_id`.

## Choices that matter for behaviour

- **Switching chats does not cancel an answer that is still streaming.** The API saves an answer
  only when the stream completes, so cancelling would lose it. The app keeps reading, ignores the
  late text, and lets the person start asking in the chat they opened.
- **A 401 is retried once after a refresh, and refreshes are single-flight.** Several calls can hit
  an expired token together; only one may spend the refresh token (tested).
- **Streaming decodes UTF-8 across read boundaries** (tested with a body cut in the middle of
  multi-byte characters). Financial answers contain "—", "€" and similar.
- **Errors are mapped to sentences** in one place (`ApiException`), including the API's own
  explanation when it says the search service is busy.
