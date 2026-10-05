# Note: publishing the Android app from the web app

## Goal
Let the Android app (`code/finance-rag-android`) be distributed from the Finance RAG web app: upload a build,
keep every version, download any of them on a phone.

## What was built (2026-10-05)
- Tables `app_releases` (version name and code, size, SHA-256, notes, uploader) and `app_release_files` (the APK
  bytes), migration `010`. Endpoints under `/api/v1/releases`; page "Android app" in the frontend.
- Admins publish and delete; any logged-in user can download. The latest version is the one with the highest
  version code.

## Decisions and why
- **The APK is stored in PostgreSQL, not on a volume.** The API pod has no persistent volume, so files written
  to disk would vanish on every deploy. A new volume means a new thing to manage and back up; the database is
  already persistent and backed up, and a few APKs of ~7 MB are small. The bytes live in their own table so
  listing releases never reads them. Revisit if files get large (the cap is 50 MB) or numerous.
- **Downloads use a 2-minute signed link, not the login header.** A plain browser link cannot send an
  `Authorization` header, and putting the login token in a URL would leak it into logs and history. The link is a
  JWT of type `download`, bound to one release. The API only accepts type `access` for its own endpoints, so the
  link opens nothing else, and a login token does not open the file. Tested both ways.
- **Version name and code are typed in, not read from the APK.** Reading them needs Android's binary manifest
  parser. The form pre-fills the name from the file name and suggests the next code; a duplicate code is a 409.
- **The file is checked to be a zip with `AndroidManifest.xml` and `.dex` code**, so a wrong file is caught.
  That is a guard against mistakes, not proof of safety: only admins can upload, and the SHA-256 is displayed.
- **The download name is built from the version** (`finance-rag-0.1.0.apk`), never from the uploaded name.

## A bug found on the way (affects other endpoints)
`get_db` commits only after the response has been sent (this FastAPI version runs dependency exit code after
the response). A client that asks for something right after a write can arrive first: the first live upload
returned 201 and a download link requested straight after got 404, because the 7 MB insert had not committed.
Fixed by committing before returning in publish and delete, and in the **Users** page's create-user and
change-role endpoints, which had the same race (the page reloads its list straight after). Rule: an endpoint
whose result the caller reads back immediately must `await db.commit()` before it returns.

## Chat history that "disappeared"
- Before 2026-10-05 ~11:35 UTC chats were not stored on the server at all; a question's only record was the
  audit trail. v0.3.0 also removed the browser-stored conversation. So earlier questions did not show.
- `app/backfill_chats.py` copies audit questions (with answers and sources) into chats. Run for user `gka`:
  2 chats restored. Admin's earlier questions were test traffic and were not restored.

## Not verified
- Downloading and installing from a real phone's browser (the APK is served as an attachment and was checked
  with a browser and with HTTP clients; Android's own install prompt was not seen).
