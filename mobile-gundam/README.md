# Mobile Gundam — agent / phone bridge (prototype 0.1)

A reusable relay for Android diagnostics and **files of any type**: APKs, ZIPs, documents, screenshots, logs and source assets. A phone-side companion sends file content and feedback to a session; a developer agent can retrieve them. The relay also carries agent-to-phone commands for future supported operations.

**Status:** The Python relay, file circulation, role-separated pairing, diagnostic events and command transport are implemented and locally tested. The Android app is source-ready but its APK has not been built or device-tested. The relay is not hosted. Direct injection into the existing Codex chat is not offered by the prototype; the Codex worker/agent must use the CLI (or call the HTTP API) in its environment.

## Start

Python 3.10+, no third-party packages. On the host:

```bash
export GUNDAM_ADMIN_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
python bridge.py serve --host 127.0.0.1 --port 8765
```

Publish the relay behind your own **HTTPS reverse proxy** with access control. On a separate shell (using the admin token on the host):

```bash
python bridge.py pair --server http://127.0.0.1:8765 --admin-token "$GUNDAM_ADMIN_TOKEN"
```

The pairing command returns a session ID, a phone token and an agent token. Keep tokens private. Enter HTTPS URL + session + phone token in the Android companion. Give the developer's process the session + agent token. The phone and agent can independently send/read files and events; only agents can enqueue commands.

```bash
python bridge.py events --server https://YOUR-RELAY --session SESSION --token AGENT_TOKEN
python bridge.py files --server https://YOUR-RELAY --session SESSION --token AGENT_TOKEN
python bridge.py download --server https://YOUR-RELAY --session SESSION --token AGENT_TOKEN FILE_ID output.apk
python bridge.py send --server https://YOUR-RELAY --session SESSION --token AGENT_TOKEN build.apk
```

Point the Codex agent to this repository and tell it to poll `events` or `files` while testing, inspect uploaded files, and send its next artifact with `send`. The current relay is transport, not a Codex internal-session plugin. Apps can use `MobileBridge.kt` to emit diagnostics directly from app-private diagnostic files; the companion uses Android's document picker and Sharesheet for external files.

## Android

Open `android/` in Android Studio and build `app`. The companion uses standard Android document selection and Sharesheet. Network communication requires HTTPS. It does not read other apps' private directories or other apps' system logs, and does not autonomously execute commands on the phone. Background always-on behavior, live Codex MCP connection and optional device-control permissions are subsequent modules.

## Transport contracts

- `POST /v1/pair` (admin bearer): create session with role-specific tokens.
- `POST /v1/s/{session}/events` (either role): JSON diagnostic or feedback event.
- `GET /v1/s/{session}/events?after=N`: cursor-based stream of events.
- `POST /v1/s/{session}/files` (either role): raw binary, with `X-File-Name` header URL-encoded.
- `GET /v1/s/{session}/files`: list files and SHA-256 digests.
- `GET /v1/s/{session}/files/{id}`: download raw file bytes.
- `POST /v1/s/{session}/commands` (agent only): queue declarative command.
- `GET /v1/s/{session}/commands?after=N` (phone only): poll commands.

Stored files are content-hashed, session-isolated and bounded to 256 MB each by default. The server uses SQLite and a filesystem blob store. Run behind TLS; limit access and implement expiration/deletion before opening it to untrusted users. Pairing credentials and transfer content are confidential.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Ownership

Project concept and requested design: Slavko Stojnić. Implementation in this repository is AI-assisted. See `CLAIM.md` and the existing `IPClaim` materials for the project owner's asserted claims, supporting evidence and limitations. Timestamping is evidence of existence, not a granted patent or automatic legal monopoly on an idea.