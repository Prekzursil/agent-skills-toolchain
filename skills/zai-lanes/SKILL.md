---
name: zai-lanes
description: Free GLM web lane (MCP glm_chat) and official plan-entitled ASR/TTS (zai-asr) — usage, modes, refresh, limits. Use when the task needs free GLM chat, or transcription/synthesis without wallet billing.
---

# zai-lanes — free GLM + unmetered-cash ASR/TTS

## Lane A — free GLM chat (MCP: `zai-lane-a`)

Tools available to Claude/Codex/ZCode via the synced MCP server:

- `glm_chat(prompt, mode=flash|think|max, web_search=bool, chat=<ref>)` — free consumer
  GLM-5.3-Flash class. `chat` ref continues a conversation (server-side context; verified
  memory across calls).
- `glm_stream(prompt, mode)` — same, streams partials via progress notifications.
- `glm_conversations()` / `glm_status()`.
- `glm_vision(prompt, image_path)` — free multimodal (image upload, GLM-5.3-Flash web vision).
- `glm_cleanup()` — delete lane-created chats (profile hygiene).
Calls are serialized (single browser); expect ~5-20 s each.

Modes: `flash` = fast; `think` = Deep Think; `max` = Deep Think+Max reasoning.
HTTP form: `python D:/bolt/enum/pulls/zai-entitlement-fuzz_2026-09-19/zai-anon-mcp.py http 18319`
→ OpenAI-compatible `/v1/chat/completions` (models `glm-web`, `glm-web-think`, `glm-web-max`;
`stream:true` supported).

Constraints: browser-backed (headed Playwright, `~/.zcode/web-profile`) — one call at a
time, ~5–20 s latency, DOM-dependent. Session refresh: `python zai-anon-mcp.py login`.
Do NOT use for anything needing >8k-word outputs or strict latency; use the coding plan
(lane: official API) for that.

## Lane C — official ASR/TTS (plan-entitled, wallet-free)

```
python D:/bolt/enum/pulls/zai-entitlement-fuzz_2026-09-19/zai-asr.py transcribe <audio>
python D:/bolt/enum/pulls/zai-entitlement-fuzz_2026-09-19/zai-asr.py tts "<text>" out.mp3 [voice]
```
Word timestamps, speaker labels, ≤45 MiB / ≤1700 s chunks (auto 16k mono mp3 via ffmpeg).
Identity: `~/.zcode/official-identity.txt` (env `ZAI_OFFICIAL_IDENTITY_FILE`). Tokens ~1 h:
refresh with `python zai-refresh.py` (browser authorize → zcode:// handler → exchange).
Metering: audio-seconds against the Coding Plan quota; the paygo wallet is never charged.
COST LEVER (measured): `--speed 2.0` halves billed quantity (5.652 -> 2.88 audio-seconds)
with a perfect transcript on clear speech — pitch-preserving atempo; use 1.5 for harder
audio. `--trim-silence` cuts latency (silence is already unbilled). Identical files are
hash-cached client-side.
Prefer this over whisper/local ASR for accuracy and long-audio chunking.
