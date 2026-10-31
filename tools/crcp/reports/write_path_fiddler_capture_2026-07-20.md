---
title: write_path_fiddler_capture_2026-07-20
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/write-path-fiddler-capture-2026-07-20
---

# ChatGPT write-path capture (2026-07-20)

## Capture path
- **Primary:** Chrome DevTools MCP (logged-out guest session on chatgpt.com)
- **Fiddler MCP:** online, port **8866**, logged in; LiveTraffic works for Fiddler-proxied Chrome chrome:// noise only
- **Fiddler gap:** `isSystemProxyEnabled=false`, `isNetworkCaptureEnabled=false`; MCP has **no** enable-system-proxy / enable-network-capture tools
- Proxied Chrome (`--proxy-server=127.0.0.1:8866 --disable-quic`) still produced **zero** chatgpt.com sessions in Fiddler (likely cert/trust or app-bound TLS)
- Desktop process: `OpenAI.Codex` Store app `ChatGPT.exe` — needs Fiddler **System Proxy** or **Network Capture** toggled in UI for DESKTOP POST capture

## Proven successful send (guest)
`POST https://chatgpt.com/backend-anon/f/conversation` → **200** `text/event-stream` (assistant replied "OK")

Target route header maps auth path:
- `x-openai-target-path: /backend-api/f/conversation`
- wire path for guest: `/backend-anon/f/conversation`

## Sequence (bot defense + conduit)
1. `POST .../sentinel/chat-requirements/prepare` body `{"p":"<vm fingerprint token>"}` → `prepare_token` + turnstile challenge
2. `POST .../sentinel/chat-requirements/finalize` body `{prepare_token, proofofwork, turnstile}` → **token** (~540s TTL)
3. `POST .../f/conversation/prepare` → **conduit_token** (`x-conduit-token`)
4. `POST .../f/conversation` with sentinel + conduit headers + SSE body

## Required request headers on chat send
| Header | Role |
|--------|------|
| `openai-sentinel-chat-requirements-token` | finalize token |
| `openai-sentinel-proof-token` | PoW |
| `openai-sentinel-turnstile-token` | Turnstile |
| `x-conduit-token` | from conversation/prepare |
| `oai-device-id` | stable UUID (cookie oai-did) |
| `oai-session-id` | session UUID |
| `oai-language` | e.g. en-US |
| `oai-client-version` | prod-… hash |
| `oai-client-build-number` | numeric |
| `Accept` | `text/event-stream` |
| `User-Agent` | real Chrome, not CRCP/* |
| `Content-Type` | application/json |
| `Origin` / `Referer` | https://chatgpt.com/ |

Auth mode additionally needs `Authorization: Bearer <access>` + `ChatGPT-Account-Id`.

## Request body schema (redacted; guest first turn)
```json
{
  "action": "next",
  "messages": [{
    "id": "<uuid>",
    "author": {"role": "user"},
    "create_time": 1784515580.535,
    "content": {"content_type": "text", "parts": ["..."]},
    "metadata": {
      "selected_github_repos": [],
      "selected_all_github_repos": false,
      "serialization_metadata": {"custom_symbol_offsets": []}
    }
  }],
  "parent_message_id": "client-created-root",
  "model": "auto",
  "client_prepare_state": "none",
  "timezone_offset_min": -180,
  "timezone": "Europe/Bucharest",
  "history_and_training_disabled": true,
  "conversation_mode": {"kind": "primary_assistant"},
  "enable_message_followups": true,
  "system_hints": [],
  "supports_buffering": true,
  "supported_encodings": ["v1"],
  "client_contextual_info": {
    "is_dark_mode": true,
    "time_since_loaded": 132,
    "page_height": 861,
    "page_width": 929,
    "pixel_ratio": 1,
    "screen_height": 1080,
    "screen_width": 1920,
    "app_name": "chatgpt.com",
    "has_web_push_capabilities": true,
    "web_push_notification_permission": "default"
  },
  "paragen_cot_summary_display_override": "allow",
  "force_parallel_switch": "auto"
}
```

## Why prior CRCP probes got 403 Unusual activity
1. Missing **entire sentinel gate** (requirements + PoW + turnstile headers)
2. Missing **conduit prepare** (`x-conduit-token`)
3. Wrong endpoint likely (`/backend-api/conversation` vs `/backend-api/f/conversation`)
4. Synthetic UA `CRCP-write-path/0.1`
5. Body used random UUID parent instead of literal **`client-created-root`** for new chats; omitted modern fields

## Next steps
1. Owner: Fiddler UI → enable **System Proxy** or **Network Capture**, send one message in Desktop ChatGPT → re-query LiveTraffic for authenticated Desktop headers (app_name / electron flags)
2. Implement sentinel solver OR browser-rail send (CDP/Playwright logged-in) OR capture-and-replay conduit/sentinel from a short-lived browser session
3. Update CRCP `write_path` body to match schema; endpoint `/backend-api/f/conversation`