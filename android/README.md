# Finance RAG for Android

This folder is the Android app, inside the `finance_rag` repository (the web app and API are one level up).

A native Android client (Kotlin + Jetpack Compose) for the Finance RAG API at
`https://finance.tekbridge.co.za`. Log in, ask questions about your financial
documents, and read streamed, source-grounded answers. Past chats are saved on the
server, follow-up questions work, and every answer shows the passages it came from.

**Nothing secret is in this repository.** The only configuration committed is the public
API address. Passwords are typed at runtime, the login is stored encrypted with a key
that lives in the Android Keystore, and the signing key is kept outside the repo.

## What it does

- Log in with the username and password an administrator gave you (there is no sign-up).
- **Your own server**: tap the "Server:" line on the login screen to enter the address of a
  different Finance RAG server. Leave it empty to go back to the standard one. It must be an
  `https` address, and it can only be changed while logged out, so a login is never sent to a
  server other than the one that issued it.
- Ask a question; the answer streams in as it is written, with tables and bold text rendered.
- Tap a numbered source under an answer to read the exact passage it was built from.
- Ask a follow-up ("and services?"). The app shows what the question was understood as.
- Open the menu to switch between saved chats or start a new one.
- Open **Documents** from the menu to upload a PDF (up to 50 MB), see your documents, delete one,
  or share one with another person by their email address.

Not built yet: checking an answer's quality score, admin screens. Those exist in the web app.

## Step by step: build and install it yourself

### 1. Install what you need (once)

| Tool | Version | Notes |
|---|---|---|
| JDK | 17 or newer | `java -version` should print it |
| Android SDK | platform **35**, build-tools **35.0.0** | Easiest: install [Android Studio](https://developer.android.com/studio) and open *SDK Manager* |

Tell Gradle where the SDK is, by either setting `ANDROID_HOME`
(macOS default: `~/Library/Android/sdk`) or creating `local.properties` in this folder:

```properties
sdk.dir=/path/to/your/Android/sdk
```

### 2. Get the code and run the tests

```bash
git clone https://github.com/grahamkatana/finance_rag.git
cd finance_rag/android
./gradlew testDebugUnitTest
```

The first run downloads Gradle and the dependencies (a few minutes, about 1 GB).
The tests use a fake server, so they need no phone, no emulator and no login.

### 3. Build an APK you can install straight away (debug)

```bash
./gradlew assembleDebug
```

The file is `app/build/outputs/apk/debug/app-debug.apk`. It is signed with a debug key
Android Studio generates for you, which is fine for your own phone.

### 4. Build the release APK (what you actually keep on your phone)

A release APK is signed with *your own* key. Make the key once, **outside this folder**:

```bash
mkdir -p ~/.android-keystores
keytool -genkeypair -keystore ~/.android-keystores/finance-rag-release.jks \
  -alias finance-rag -keyalg RSA -keysize 4096 -validity 10000 \
  -dname "CN=Your Name, O=Personal, C=ZA"
```

`keytool` asks you for a password (use a long one). **Back up the `.jks` file and its
password in a password manager.** If you lose either, you cannot update the app in place
later; you would have to uninstall it and lose its saved login.

Next, tell Gradle where the key is. Create `keystore.properties` in this folder
(it is git-ignored, so it never reaches GitHub):

```properties
storeFile=/Users/you/.android-keystores/finance-rag-release.jks
storePassword=the-password-you-chose
keyAlias=finance-rag
keyPassword=the-password-you-chose
```

Build and check it:

```bash
./gradlew assembleRelease
$ANDROID_HOME/build-tools/35.0.0/apksigner verify --verbose app/build/outputs/apk/release/app-release.apk
```

You want to see `Verifies`. The file is `app/build/outputs/apk/release/app-release.apk`.
Without a `keystore.properties`, the release build still works but produces an
**unsigned** APK, which Android will refuse to install.

### 5. Put it on your phone

**Option A, with a cable (recommended).**
1. On the phone: *Settings → About phone*, tap *Build number* seven times, then
   *Settings → System → Developer options → USB debugging* on.
2. Connect the phone, accept the "Allow USB debugging?" prompt, then:
   ```bash
   adb devices                 # your phone should be listed as "device"
   adb install -r app/build/outputs/apk/release/app-release.apk
   ```

**Option B, without a computer cable.**
1. Get the APK onto the phone (Google Drive, email to yourself, a USB file copy).
2. Open it from the phone's *Files* or *Drive* app. Android asks to allow
   *Install unknown apps* for that app: allow it once, go back, and tap *Install*.
3. Play Protect may say the app is from an unknown developer. That is expected for any
   app you built yourself; choose *Install anyway*.

Open **Finance RAG**, log in, and ask a question.

### 6. Updating the app later

Raise `versionCode` (and `versionName`) in `app/build.gradle.kts`, run `assembleRelease`
with the **same keystore**, and install over the old one with `adb install -r` or Option B.
Your login is kept.

### 7. Publish it in the Finance RAG web app

Instead of passing the APK around by hand, an administrator can publish each build in the web app
(**Android app** page, "Publish a version"). Every version is kept, and anyone with a login can open that
page on their phone and tap **Download APK**. Use the same **version name** and **version code** as in
`app/build.gradle.kts`; the web app refuses a code that is not higher than the previous one. The page shows the
file's SHA-256 so a download can be checked against what was published.

## Pointing the app at a different server

Create (or edit) `local.properties` and rebuild:

```properties
api.baseUrl=http://10.0.2.2:8000
```

`10.0.2.2` is how the Android emulator reaches your computer. **Debug builds** may use plain
`http://` for `10.0.2.2` and `localhost` only; **release builds never allow plain HTTP**.
Delete this line before building the release APK, or it will be built into it.

## Before you push to a public repository

This project lives inside the `finance_rag` repository, which has its own ignore rules too (`.gitignore` and `.dockerignore` at the root).

```bash
git ls-files | grep -Ei 'keystore|\.jks|local\.properties|\.apk|\.env' && echo "STOP: a secret or build file is tracked" || echo "clean"   # run from the repository root
git grep -nEi 'password|secret|token|api[_-]?key' -- ':!README.md' ':!notes' ':!app/src/test' ':!app/src/main/java'
```

The first command must print `clean`. The second should find nothing in build files. (Source
files mention these words only as variable names.)

## How it is built

```
app/src/main/java/com/graham_katana/financerag/
  data/   ApiClient (login, automatic token refresh, streaming, documents), TokenStore (Keystore), Models
  ui/     LoginScreen, ChatScreen, DocumentsScreen, MarkdownText, view models, theme
app/src/test/                  JVM unit tests: API client (fake server), view models, markdown parser
notes/                         why each decision was made (read these before changing anything)
```

Dependencies are few and each one has a recorded reason in `notes/002-stack-choices.md`.
House rules for contributors and AI assistants are in `AGENTS.md`.

## Security notes

- **No secrets in the repo**: no keys, tokens, passwords or `.env` files. The signing key and
  its password live outside it. See `.gitignore`.
- **Login storage**: the access and refresh tokens are encrypted with an AES-256 key held in
  the Android Keystore (it cannot be exported), and Android backup is switched off.
- **Network**: HTTPS only in release builds. Tokens are never logged.
- **An expired login** is renewed silently; if it cannot be, the app returns to the login screen.
- The app cannot do more than the logged-in account can; permissions are enforced by the API.
