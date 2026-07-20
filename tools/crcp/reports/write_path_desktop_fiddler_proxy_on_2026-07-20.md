# Desktop capture note (Fiddler system proxy ON) — 2026-07-20

## Confirmed
- Fiddler `isSystemProxyEnabled=true`
- Desktop process originator: **Codex Desktop** (Store ChatGPT.exe / OpenAI.Codex)
- LiveTraffic includes decrypted `GET https://chatgpt.com/backend-api/wham/usage` (200)
- Auth headers present on Desktop API:
  - Authorization: Bearer <jwt>
  - ChatGPT-Account-Id / chatgpt-account-id
  - oai-language: en-US
  - originator: Codex Desktop
  - User-Agent: Chrome/150 desktop string
  - cookies: oai-sc, _puid, __cf_bm, __cflb
  - Sentry baggage: sentry-release=codex@26.715.31925

## Missing (as of this note)
- No `POST .../f/conversation` or `.../conversation` in LiveTraffic yet
- No sentinel chat-requirements prepare/finalize from Desktop yet

## Action needed
Owner: send **one short chat message** in Desktop ChatGPT while System Proxy stays on.
Then agent re-queries Fiddler for POST /f/conversation + openai-sentinel-* headers.

## Security
Full Bearer JWT appeared in Fiddler MCP session dump — treat as sensitive; do not commit.
