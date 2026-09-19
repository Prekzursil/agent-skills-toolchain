# MCP / memory runtime parity audit — 04.09.2026

**valid_as_of:** 2026-09-04
**provenance:** disk-verified receipts under `.agents/mcp-parity-2026-09-04/` plus this session’s TCP/HTTP probes. Workflow `mcp-runtime-parity` completed; its synthesizer wrote **no** durable file (scratch was the empty fallback string). The verify panel then fail-closed (`confirmed: []`). That is **not** a refute of the P0s below.

**Do not** treat `inventory.md` `BM-DOWN :18765` as live. Detector probes retired `:8765` then names `:18765` (self-contradicting). Superseded by `memory-audit.md`.

## Executive verdict

You were right: the tools do **not** share one MCP plane. Claude is the widest merge-fed surface. Cursor is an intentional G-6 park. Codex is 4 registry + 3 local. Z.ai is merge + native pack. **Grok is hand TOML plus a second marketplace plugin MCP plane**, not in `VALID_TARGETS`, not in `sync_shared_state.ps1`.

**Full surface-parity (Claude’s 51/74 on every runtime) is REJECTED** (RAM: 6 GiB idle MCP budget, Cursor hexstrike OOM, Hermes 17 hubs already 529 tools). **Policy-parity** is the estate contract: declared subsets, no silent second configs, **basic-memory on `:18765` everywhere**.

TIER-0 applied this session (backup-first): Grok keepers retargeted `:8765→18765` and `:8812→18812`; `agent-mail` enabled and removed from `disabled_mcp_servers`. **Takes effect on the next Grok session**, not this one. Daemon was not restarted.

## Parity matrix

| Runtime | Live MCP | Sync | Second definition surface | Memory path | Health |
|---|---|---|---|---|---|
| Claude Code | 74 top-level / 51 generated / ~19 UI-on | merge | `~/.mcp.json` (21) + 23 live extras + plugins | HTTP `:18765` | path OK / live NOT-CHECKED |
| Codex | 7 (4 registry + 3 local) | merge | plugin cache `.mcp.json` (not the live map) | HTTP `:18765` (+ `~\.codex\memories\`) | path OK / live NOT-CHECKED |
| **Grok** | 22 TOML + **19 plugin MCP** | **none** | **YES** — marketplace `.mcp.json` | was `:8765` (dead); **now `:18765`** | this session: BM tools **absent** (stale URL) |
| Cursor | **6** (G-6) | merge (claude-mirror + park) | plugin enable-list all **off** | shim → `:18765` | path OK / live NOT-CHECKED |
| ZCode / Z.ai | 20 (16 registry + leftovers) | merge | plugin `.mcp.json`; z.ai 4 are **in** registry | HTTP `:18765` + `cli/memories/` | path OK / second store |
| Hermes | 17 HTTP | deploy | vendor `optional-mcps` | BM + native `memories/` | path OK |
| Goose | BM + agent-mail | none | XDG vs AppData dual yaml | HTTP `:18765` | path OK / search path UNVERIFIED |
| Agy | 33 mostly stdio | none | `mcp_config.json` ×2 | **no BM** | vault-orphaned skills |

## Dual-config (the “second MCP just for him”)

**Grok:** surface-1 `config.toml` `[mcp_servers.*]`; surface-2 trusted plugin `.mcp.json` (19 names: firecrawl, tavily, tinyfish, exa, context7, cloudflare-*, discord, …). Name ∩ with TOML is **empty**. That is why some tools show more working MCPs.

**Also split-brain in the same Grok file:** `disabled_mcp_servers` listed huggingface/notion/linear/brightdata while their tables said `enabled=true`.

**Claude:** merge writes `.claude.json`; `~/.mcp.json` is a second file. `disabledMcpServers` (131 names) hides 55 of 74 live keys.

**Cursor:** single loaded map. Same-day bak had 13 (G-6 + 7 Hermes hubs); default merge cleared them.

## Memory

Shared BM daemon: **UP** on `:18765` (TCP listen python 50552; `GET /mcp` = 406 = alive; initialize POST = 200 SSE `Basic Memory 4.0.0b1`). Retired `:8765` closed (Hyper-V exclusion migrate 04.09.2026).

| Why Grok was red | Evidence |
|---|---|
| Wrong port (sufficient) | `config.toml` still `:8765` until this session’s TIER-0; contract/agents.json `:18765` |
| Possible second class after URL fix | Grok raw HTTP vs BM streamable-http + `Mcp-Session-Id`. Cursor needed `bm_cursor_http_session.py` for stale-session. **Not reproduced on 18765 yet.** |

Cursor 27.08 red was **client stale after watchdog restart**, not daemon death. Do not treat a red User-scope badge as BM-down.

Agent-mail live `:18812` open. Grok had it **disabled** on `:8812`.

## P0 / P1 (scoped)

| ID | Verdict | Scope |
|---|---|---|
| GROK-NO-MERGE | **REAL** | no `grok` in `VALID_TARGETS`; no `merge_generated_grok_mcp.py`; 0 grok hits in `sync_shared_state.ps1` |
| DUAL-SURFACE | **REAL** | Grok plugin `.mcp.json` 19 vs TOML 22; Claude `~/.mcp.json` |
| BM-DOWN | **OVERCLAIM** | daemon up on 18765; Grok client was on 8765 |
| GROK-KEEPERS-STALE-PORT | **REAL** | TIER-0 URL retarget applied this session |
| CURSOR-13-HUBS | **NOT LIVE** | bak only; live is G-6 |
| ZCODE-SECOND-MEMORY | **REAL** | `cli/memories/` parallel to BM (G-81 adjacent) |
| LITERAL-SECRET-PRESENT | **REAL** | Grok + Codex `mcphub` `Authorization` keys. NEVER-ROTATE |

Workflow verify `confirmed: []` / `refuted: [GROK-NO-MERGE, BM-DOWN-OR-CLIENT, DUAL-SURFACE]` is **instrument failure** (empty synthesizer). Independent file reads keep GROK-NO-MERGE and DUAL-SURFACE real; BM-DOWN-OR-CLIENT is the overclaim above.

## Gem-hunt decision-queue

**TIER-0 (this session):** Grok BM/mail URLs + enable agent-mail. Restart this Grok CLI to pick them up. Then `grok mcp doctor basic-memory`. If handshake still fails on 18765, reuse Cursor shim (do not invent a third client).

**TIER-1 (BUILD, keepers-only — not Claude-51):**
1. Add `"grok"` to `VALID_TARGETS`.
2. `merge_generated_grok_mcp.py` cloned from Codex TOML merge; safe-default = BM + agent-mail HTTP; skip plugin-provided names; emit SSOT URLs.
3. Pin `[compat.claude] mcps = false` and `[compat.cursor] mcps = false` so Claude’s 51 does not dump in.
4. `x_grok` authMode `oauth|bearer|none` before merging GitHub/Notion (Grok OAuth ≠ Codex PAT).
5. Park Grok `search-hub` stdio; park hermes-only `*-hub` copies on Grok; park plugin duplicates of hosted firecrawl/tavily.

**SKIP:** surface-parity 51-everywhere; `--attach-all-safe` Cursor; remount hexstrike on Cursor; Mem0/Graphiti; OpenRouter MCP; restart BM from this audit.

**TIER-2:** Goose/Agy onto the plane only after skills-path evidence; fold ZCode/Hermes/Codex native `memories/` behind G-81 or document as read-only.

## Evidence

- Inventory: `.agents/mcp-parity-2026-09-04/inventory.md` (mechanical; BM finding superseded)
- Memory: `memory-audit.md` (disk-verified 18765 UP)
- Dual-config: `dual-config.md`
- Runtime lenses: `runtime-{claude,codex,grok,cursor,zcode,rest}.md`
- Gems: `gem-{competitive,prune,native,wildcard}.md`
- Control plane: `mcp_control_plane.py:15`; `sync_shared_state.ps1` (no grok merge)
- Grok backup: `~\.grok\config.toml.bak-20260904-bm-port`

UNIT-COMPLETE: mcp-parity-audit
