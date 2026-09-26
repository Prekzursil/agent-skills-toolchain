---
title: sessions-catalog-2026-08-27
type: note
permalink: main/sessions/sessions-catalog-2026-08-27
---

# Sessions catalog 2026-08-27

Cross-AI session catalog now exists and is re-runnable.

- **Catalog:** `C:\Users\Prekzursil\.agents\session-catalog.md` — one pointer line per session
  (date, title/first-snippet, path), grouped by runtime, secrets redacted, snippets
  truncated to 200 chars.
  *(Moved out of the vault 27.08.2026: inside the vault the 378 KB file became an
  oversized embedding entity — 1,482 chunks at batch_size=2 — whose vector sync
  stalled the daemon's MCP surface and caused the watchdog kill/flap loop; see
  `.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` § Flap root cause.)*
- **Indexer:** `C:\Users\Prekzursil\.agents\scripts\index-ai-sessions.py` — idempotent
  (skips unchanged by path+mtime via `index-ai-sessions.state.json`), streams only
  first/last 64 KB per file, prunes stale entries per completed walker.
  Re-run any time: `python ~/.agents/scripts/index-ai-sessions.py`.
- **Counts (2026-08-27):** grok 742 (metadata-only by policy — no content read),
  codex 396, claude 174 (top-level sessions; subagent transcripts are served by
  recall-workflow-agent), cursor 119, agy 18 (workspace shadow-git dirs, no transcripts),
  goose 3. Total 1,452.
- **Not ingested on purpose:** full transcripts (RAM + vault bloat). Deep views:
  `format-codex-sessions` (Codex renderer), `recall-workflow-agent` (Claude workflow
  subagents), `codex-session-reunion` (dedupe/promote split Codex stores).