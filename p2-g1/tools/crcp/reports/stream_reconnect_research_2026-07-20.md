# Stream reconnect research — 20.07.2026

## Goal
Determine whether ChatGPT Desktop stream traces (`async_source`, `streamRequestId`) enable a live WebSocket/SSE reconnect without REST polling.

## Evidence in hand
- Stream fixtures under `fixtures/chatgpt_desktop/v1/raw_stream/` are progressive UI snapshots.
- They contain metadata hashes/lengths/directives; **not** full assistant text.
- Conversation text is available via:
  1. Full conversation export JSON
  2. **Live REST** `GET /backend-api/conversation/{id}` (proven)

## ChatGPT Desktop process surface
- Package: MSIX `OpenAI.Codex_*` / `ChatGPT.exe`
- Earlier audit: **no Listen ports** on ChatGPT PIDs
- Only ephemeral Bound ports observed
- Implication: Desktop is not exposing a documented local control API

## Electron debugging (authorized, own machine)
Options for deeper capture (owner-operated):
```text
# If Desktop supports it (may require app restart flags / developer mode):
ChatGPT.exe --remote-debugging-port=9222
# Then: chrome://inspect or Playwright CDP attach
```
Also: Fiddler/mitmproxy with system proxy + Desktop trust (HTTPS MITM on own traffic only).

## async_source / saserver-*
- Fields like `saserver-polandcentral-prod...` look like **Azure regional stream backends**
- Without a valid stream session cookie/token and streamRequestId binding, reconnect is **not proven**
- These IDs may be single-use or session-scoped

## Verdict (Phase 3)
| Approach | Status |
|----------|--------|
| REST poll bridge | **Production path** — implemented |
| Stream reconnect | **Research only** — not blocking |
| Desktop local command | **Not available** on observed Listen surface |

## Next experiments (optional, later)
1. Capture one Desktop chat with mitmproxy; extract WS/SSE URLs + headers
2. Compare Authorization: Bearer vs cookie session
3. Attempt short-lived reconnect with captured streamRequestId (expect fail if single-use)
4. If successful, replace poll interval with event-driven updates

## Recommendation
Keep **60s REST poll** as the always-on pipe. Treat stream reconnect as an optimization only after a successful capture log is filed under `reports/stream_capture/`.
