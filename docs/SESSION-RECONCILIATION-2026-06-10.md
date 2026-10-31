---
title: SESSION-RECONCILIATION-2026-06-10
type: note
permalink: dqverify-repo-20261013/docs/session-reconciliation-2026-06-10
---

# Session Reconciliation — 2026-06-10

Snapshot of toolchain reality after a large infrastructure + tooling session. Covers
new skills, new MCP servers, the cross-AI unification, and Codex fixes.

## New skills (added to `skills/`)

Four game reverse-engineering skills that orchestrate the local RE MCP fleet
(Binary Ninja, Ghidra, Cheat Engine, Frida):

| Skill | Purpose |
|-------|---------|
| `game-re-binary` | Static analysis pipeline (Binary Ninja → Ghidra → Cheat Engine): orient → map surface → find targets → decompile |
| `game-frida-trace` | Frida dynamic tracing: enumerate → attach → hook → collect |
| `game-find-anticheat` | Identify/map anti-cheat (EAC, BattlEye, Vanguard, FACEIT, VAC…) static + live |
| `game-unpack-pe` | Unpack/unprotect PE (UPX/VMProtect/Themida): packer ID → OEP → dump → fix IAT |

The SWFOC (`swfoc-modding`, `swfoc-reverse-engineering`, `swfoc-runtime-address-hunting`)
and `battlecats-event-unlock` skills are confirmed present and were re-linked into both
Claude Code and Codex this session.

## New MCP servers

| Server | What | Where |
|--------|------|-------|
| **ocr** | Multi-engine OCR (RapidOCR + Tesseract + ABBYY FineReader 16) with CER/WER accuracy evaluation + engine comparison | separate public repo: `Prekzursil/abbyy-finereader-ocr-mcp` (code at `D:\mcp-servers\abbyy-finereader-ocr-mcp`) |
| **basic-memory** | Durable, semantically-searchable markdown+vector memory (sqlite-vec + FastEmbed), vault on D:, 154 migrated notes | `D:\.basic-memory` (junctioned from `~/.basic-memory`) |
| **firefox-devtools** | Mozilla Firefox DevTools MCP (`@mozilla/firefox-devtools-mcp`), headless WebDriver BiDi | npx, user scope |

`basic-memory` is wired for **compaction survival**: a PreCompact hook writes a
searchable checkpoint into the vault; a CLAUDE.md rule has Claude query basic-memory
(`build_context`/`search_notes`) after compaction. Memory = recall, not retention.

## Cross-AI unification (single source of truth)

Both Claude Code and Codex now share tools via **mcp-funnel over stdio**:

- **Dedup**: removed direct server defs that the funnel already provides. Claude
  `mcpServers` 50→20; Codex `[mcp_servers.*]` 37→13. The shared ~30 servers are defined
  ONCE in `~/.mcp-funnel-master.json`, lazy-loaded via funnel's `discover_*`/`load_toolset`.
- **Profiles**: `scripts/mcp-profile.ps1 <default|minimal|re|web|quality|data>` switches
  active server sets without per-session disabling.
- **Skills unified**: canonical set at `~/.agents/skills`; `~/.claude/skills` symlinks to it,
  `~/.codex/skills` has per-skill junctions to it (preserving Codex `.system/` built-ins).
- ⚠️ Funnel reached over **stdio not HTTP** (Claude Code doesn't defer HTTP MCP tool schemas).

## Codex fixes

- `spawn_agent` 400 error (`encrypted parameters … not configured for this model`) fixed by
  disabling `multi_agent`, `multi_agent_v2`, `enable_fanout` in `config.toml [features]`
  (broken with gpt-5.5 in Codex 0.139.0). Re-enable when OpenAI ships gpt-5.5 encrypted-tool support.
- Known/minor: `postgres`+`sonarqube` need Docker running; `huggingface` needs `codex mcp login`;
  `figma` uses a deprecated npm package.

## Counts (today)

- Repo `skills/`: **158** (was 154).
- Live `~/.agents/skills`: ~288 (canonical, shared by both AIs).
- MCP servers: Claude 20 direct + ~30 via funnel; Codex 13 direct + funnel.