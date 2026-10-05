# 003 — Build, signing, and what has and has not been verified

## Signing
- The release key is generated with `keytool` into `~/.android-keystores/` (outside the repo). Its
  password is only in the git-ignored `keystore.properties`. `.gitignore` also blocks `*.jks`,
  `*.keystore`, `*.p12` and `local.properties`.
- With no `keystore.properties` the release build produces an unsigned APK, which cannot be
  installed: a missing key fails loudly instead of silently shipping a debug-signed release.
- **Back up the key.** Losing it means users must uninstall to update.

## Why release builds have R8 (minification) off
R8 and kotlinx.serialization are a known source of crashes that only appear in release builds. A
release build has not yet been run on a device (see below), so shrinking is off. Turning it on is a
one-line change in `app/build.gradle.kts`; do it once a release build has been exercised on a phone.
The cost is a 7 MB APK instead of roughly 3 MB.

## Debug-only cleartext
`app/src/debug` allows plain HTTP to `10.0.2.2` and `localhost` so the app can be tried against a
local server from an emulator. It lives in the debug source set, so a release APK cannot contain it
(checked: the release APK has no `network_security_config`).
`local.properties` can override the API address; delete it before a release build.

## What was verified, and how (2026-10-05)

| Claim | How it was checked |
|---|---|
| 47 unit tests pass | `./gradlew testDebugUnitTest`, no device. Covers the API client against a fake HTTP server (login, 401 then refresh then retry, single refresh for concurrent calls, 429, 503, 404, streaming, multi-byte text split across reads), both view models, and the markdown parser. |
| The tests can fail | Mutation check: removing the refresh single-flight guard made exactly the test written for it fail; the guard was restored. |
| The networking layer works against the real API | A throwaway JVM test (deleted, not committed) ran against `finance.tekbridge.co.za`: wrong password rejected, login, expired access token refreshed automatically, streamed answer saved with 3 sources, and a follow-up rewritten by the API. The test chat was deleted afterwards. |
| The release APK is signed and clean | `apksigner verify` (v2 scheme, 1 signer); `zipalign -c`; not debuggable; only the INTERNET permission; no cleartext config; the API address in the DEX is `https://finance.tekbridge.co.za` and `10.0.2.2` is absent; a scan for key, token and password patterns, and for the known passwords, found nothing. |

## What was NOT verified
- **The screens have never been run.** The only Android emulator on the machine (Pixel 7, API 36)
  could not run usably on an 8 GB Intel Mac: its System UI repeatedly stopped responding, with a
  guest load average around 40, even with host-GPU rendering. So login, the chat screen, the
  drawer, the sources sheet and the launcher icon were not seen running on any device. A debug APK
  did install on it and its login screen text was read through uiautomator once, but nothing past
  that. The Compose code compiles and its logic is unit tested; its layout and look are untested.
- **`KeystoreTokenStore` has not run.** It needs a device (AndroidKeyStore does not exist on the
  JVM). If it fails, the login screen reports "this device could not store the login securely"
  instead of crashing (covered by a test of the view model), but the happy path is unproven.
- **A release-mode run** (the build that goes on the phone) has not happened.

The first thing to do with the APK on a real phone is: log in, ask a question, open a source, close
and reopen the app (the login should persist), and switch to a saved chat. Report anything that
differs from this note.
