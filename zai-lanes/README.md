# zai-lanes — Z.AI free/plan lane tooling (operator estate, 2026-09-19)

Extracted from engagement `D:\bolt\enum\pulls\zai-entitlement-fuzz_2026-09-19\` (receipts there).

## Lane A — free consumer GLM (`zai-anon-mcp.py`)

- MCP server (stdio) + OpenAI-compat HTTP bridge (`http [port]`, default :18319).
- Tools: `glm_chat(prompt)`, `glm_status()`. Model class: GLM-5.3-Flash web (`x-preview-l`),
  Deep Think available. Free consumer tier, zero metering.
- Backend: dedicated headed Playwright profile `~/.zcode/web-profile` (G-90 isolated).
  Aliyun invisible captcha passes ONLY in real (headed) browser contexts — headless is
  blocked at the captcha layer (measured; not profile-warmth). Idle reaper closes the
  browser after 10 min (RAM discipline).
- Session: `~/.zcode/web-session.json` (chat.z.ai `token` cookie JWT). Refresh: run
  `python zai-anon-mcp.py login` (headed one-time login on the same profile).
- Wired: `.agents/agents.json` SSOT `zai-lane-a` (targets claude+codex+zcode), materialized
  via sync_shared_state.ps1 → Claude global + Codex TOML + ZCode config. Cursor: parked by
  its curated attach list (documented gap).

## Lane C — official plan-entitled ASR/TTS (`zai-asr.py`, `zai-refresh.py`)

- Endpoint: `POST https://zcode.z.ai/api/v1/mcp/server/video_edit` (stateless MCP, SSE).
- Identity (BOTH required): `Authorization: Bearer <zcode token>` +
  `X-Bigmodel-Authorization: <zai access token>` — file `~/.zcode/official-identity.txt`.
- Tokens ~1h TTL; refresh: `python zai-refresh.py` (browser authorize → zcode:// handler
  capture → exchange). The zcode:// capture handler: `zcode_handler.py` + HKCU registration
  (REMOVED after capture; Desktop's own handler is live — re-register only to refresh
  outside the Desktop).
- Billing: audio_seconds / plan quota (MCP-tool class). Wallet never charged (1113 absent).
- Whisper-replacement: word timestamps, speaker labels, 70-min chunks, TTS w/ voice+style.

## Repo policy

PRIVATE-ONLY repo (HOME estate locks). No secrets committed: identity/session files live
under `~/.zcode/`, not here. Receipts + evidence in the engagement folder.
