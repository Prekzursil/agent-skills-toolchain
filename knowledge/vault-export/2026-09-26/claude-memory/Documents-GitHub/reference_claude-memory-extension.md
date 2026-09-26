---
name: claude-memory-extension
description: Decision on extending Claude Code memory/context — best local options,
  what to skip, verified against this machine
metadata:
  node_type: memory
  type: reference
  originSessionId: 09158d9e-df69-4e33-8371-22a2963e3d7d
permalink: main/claude-memory/documents-git-hub/reference-claude-memory-extension
---

# Claude Code Memory Extension — Decision (2026-06-10)

Researched via 8-agent workflow with adversarial empirical verification on the live machine.

## STATUS: basic-memory INSTALLED 2026-06-10 ✓
- Installed v0.21.6 via `uv tool install basic-memory` (exe shim: `C:\Users\Prekzursil\.local\bin\basic-memory.exe`).
- Registered as user-scope MCP: `claude mcp add basic-memory` with env `BASIC_MEMORY_HOME=D:\basic-memory`, `FASTEMBED_CACHE_PATH=D:\basic-memory\.models`, `HF_HOME=D:\basic-memory\.hf`, `DO_NOT_TRACK=1`. Vault "main" → `D:\basic-memory`.
- Config + DB + 64MB model dir `C:\Users\Prekzursil\.basic-memory` is a JUNCTION → `D:\.basic-memory` (so everything's physically on D:, ~0 real C: bytes). Relocate script: `C:\Users\Prekzursil\scripts\relocate-basic-memory.ps1`.
- Telemetry already off (`logfire_enabled:false`); semantic search enabled (fastembed bge-small-en-v1.5). Search verified working.
- COLD START IS SLOW (~10-15s: FastMCP init + update-ping + model load on RAM-tight box) → `claude mcp get` probe may show "Failed to connect" but the server DOES start (verified stdio transport). Set `MCP_TIMEOUT=30000`/`MCP_TOOL_TIMEOUT=30000` (User env) so new sessions wait long enough. fastmcp update 3.4.2 available (cosmetic).

## VERDICT (original analysis)
1. **Today: do nothing / harden the incumbent.** Native file memory (`~/.claude/.../memory/*.md`, ~151 notes / 0.6 MB) + the active 1M context window (Opus 4.8) + `/compact` + auto prompt-caching already cover the need. Semantic recall is MARGINAL at this scale — ripgrep finds everything instantly. Retrieve via Grep-then-Read.
2. **Upgrade when scale justifies it: `basic-memory` (basicmachines-co).** Best Claude-Code-native fit. [INSTALLED — see STATUS above]
3. **Runner-up: Qdrant embedded** (official `mcp-server-qdrant`, `QDRANT_LOCAL_PATH`) if you prefer a vendor-maintained MCP over a community product.
4. **SKIP the Azure PostgreSQL/AI Search/VM idea** — recurring cost + maintenance + latency, no integration advantage (still needs an MCP wrapper), marginal payoff at current scale. Reconsider only for multi-machine sync or thousands of notes.

## basic-memory — empirically verified on THIS box (Python 3.14.3)
- Installs CLEAN on Python 3.14.3 — the 3.14 fear is dead. `onnxruntime 1.26.0` has cp314-win_amd64 wheel; sqlite-vec, tokenizers, numpy all resolve. End-to-end embedding produced a 384-dim vector.
- **No torch** (confirmed `torch installed?: False`). Semantic search = sqlite-vec + FastEmbed (ONNX).
- Footprint: venv 238 MB, model only 64 MB (quantized). No Docker, no daemon — `uvx`-spawned stdio MCP.
- Storage = markdown (superset of current workflow, git/Obsidian-friendly).
- Real CC integration: `claude mcp add basic-memory -- uvx basic-memory mcp`, 17 MCP tools, plus a CC plugin with session-briefing + pre-compaction-checkpoint commands.

## MANDATORY before installing (machine constraints)
- C: is 96.9% full (~24.7 GB free). RAM ~90% used (~3 GB free). A 4.6 GB HF cache ALREADY sits on C:.
- **Set these to D: BEFORE first launch** or the model + caches accrete on the near-full C::
  `FASTEMBED_CACHE_PATH`, `HF_HOME`, `UV_CACHE_DIR` → D:\ paths. And `BASIC_MEMORY_HOME` → D:.
- **Single-writer caveat:** sqlite-vec is single-writer. With many parallel Claude sessions, use **per-project vaults** (`basic-memory project add` — e.g. separate SWFOC / Battle Cats vaults) so sessions hit different DBs and avoid `database is locked`.
- basic-memory ships telemetry deps (sentry-sdk, opentelemetry, openai client) as runtime deps — disable telemetry for offline-first use.

## Machine facts relevant to this decision
- PostgreSQL 18 running natively on port 5433, but pgvector NOT installed; configured `postgres` MCP is Docker-based (pgEdge) and currently broken (Docker daemon off). "Reuse Postgres" path scored only 5/10.
- Hard-disqualified on Windows: sqlite-vss (no Windows), Weaviate (Docker-only), Milvus (Docker stack), Zep/Graphiti (no Windows FalkorDB + active CVE-2026-32247).
- API memory tool (`memory_20250818`) is NOT a Claude Code feature — API-developer only.