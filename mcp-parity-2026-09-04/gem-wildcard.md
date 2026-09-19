# Gem-hunt lens: wildcard — policy-parity vs surface-parity

**UNIT-COMPLETE: gem-wildcard**
Date: 2026-09-04
Provenance: disk-verified (named files re-read this unit). Not the inventory digest alone.
No secret values. LITERAL-SECRET-PRESENT noted only as key names where peers already did.

## Question

Is "full parity" (the same 51 Claude-generated servers on every runtime) even desirable on this ~32 GB RAM box?

## Answer

**No.** Surface-parity is not desirable here. The box already chose **policy-parity**: declared per-runtime subsets, parked catalogs, HTTP hubs for Hermes, a 6 GiB idle MCP budget, and G-6 / G-11 / G-99 / G-1 / G-15 locks that exist specifically so Claude's 51 is **not** a global template.

## REC (one)

**REC-WILDCARD: Policy-parity, not surface-parity.** Value **HIGH** × effort **LOW**.

Policy-parity means:

1. Each runtime has a **declared** subset (registry `targets[]`, Cursor G-6 keep-list, Grok G-11/G-99 keepers, Hermes G-1 HTTP-only). Sync may write only that subset.
2. **No silent second configs** (marketplace `.mcp.json`, `~/.mcp.json`, disable-arrays that contradict `enabled=true`).
3. **BM works everywhere** on SSOT `http://127.0.0.1:18765/mcp` (agent-mail on `:18812`). That is the only surface that must be universal.

Surface-parity (51 names × every CLI) is **REJECTED**. Do not re-propose it. Do not implement the PLANNED-unbuilt Grok merge as a Claude-51 clone.

Immediate NATIVE action (not a new merge runtime): point Grok keepers at `:18765` / `:18812` and enable `agent-mail`. Cursor/Codex/ZCode/Hermes already match SSOT; Grok still dials dead `:8765` / `:8812`.

Do not: `--attach-all-safe` Cursor; add `grok` to `VALID_TARGETS` with Claude's 51; restore parked Grok stdio; Mem0/Graphiti; second orchestration runtime; Cursor BYOK; OpenRouter MCP. Those are DEDUP REJECTED/ABSORBED.

---

## Declared subsets already on disk (not a proposal)

| Runtime | Declared policy | Mechanism | Live (this hunt) |
|---|---|---|---|
| Claude | widest registry set | `targets` include `claude`; merge | generated **51** / targeted **54**; live top-level **74**; UI-on via `disabledMcpServers` ≈ **19** |
| Codex | tiny | `targets` include `codex` (4) + merge preserves locals | **7** names (4 registry + 3 local) |
| Cursor | G-6 core | `CURSOR_DEFAULT_APPROVED_SERVERS`; cursor ∉ `VALID_TARGETS`; merge `--write` without `--attach-all-safe` | **6** live; parked catalog **32** keys; same-day bak **13** was rolled back |
| Hermes | HTTP hubs only (G-1) | `deploy_hermes_mcp.py` | **17** HTTP |
| ZCode | mid | `targets` include `zcode` (16) | **20** live (16 registry + locals) |
| Grok | G-11/G-99 keepers BM+agent-mail | parked TOML; **no** merge; grok ∉ `VALID_TARGETS`; **no** `grok` string in `agents.json` | **22** TOML + **34** plugin IDs + **19** plugin MCP names; agent-mail **enabled=false**; BM URL still `:8765` |
| Goose | BM+agent-mail HTTP | hand; goose ∉ `VALID_TARGETS` | unique MCP **2** HTTP |
| Agy | not on control plane | hand; agy ∉ `VALID_TARGETS` | `mcpServers` **33** mostly stdio; **no** BM/agent-mail |

`VALID_TARGETS` (`mcp_control_plane.py:15`) = `{claude, codex, zcode, hermes}`. Cursor is merged as a **trim of Claude**, not as a 51-copy.

---

## Findings

### 1. SURFACE-PARITY-REJECT

- **name:** SURFACE-PARITY-REJECT
- **what:** Cloning Claude's generated 51 MCP servers onto Cursor, Codex, Grok, ZCode, Hermes, Goose, and Agy is not a goal. It is a RAM and tool-schema failure mode.
- **why-this-estate:** ~31.6 GB RAM, chronic pressure, BM daemon dies under load (watchdog near-daily force-recover, 27.08 receipt). G-26 forbids `agent worker start` while free RAM < 8 GB. G-36: one `cursor-agent` at a time. Cursor hexstrike 154-tool schema dump OOMs Fable/Composer (G-15/G-18, 2026-09-04). Hermes **17** HTTP servers already expose **529** tools (03.09.2026 receipt). Claude's 51 includes local-bridge RE stdio (ghidra, ida, frida, hexstrike, binary-ninja, cheatengine, …) that Hermes already converted to hubs to stop orphan fleets (27 stray processes killed 03.09).
- **how:** Do nothing that copies `select_servers(target="claude")` onto other runtimes. Keep per-target `targets[]`. Leave Cursor merge on SAFE_DEFAULT G-6. Leave Hermes HTTP-only. Treat Grok keepers as BM+agent-mail, not the parked stdio catalog.
- **source:** `mcp_control_plane.py:15,19-20,185-187`; `agents.json` `mcp.policy.maxPrivateBytes=536870912` and `supervision.totalIdlePrivateBytes=6442450944`; `merge_generated_cursor_mcp.py:123-141`; `HERMES-HARMONIZATION_2026-09-03.md:9-11,50-56`; `BASIC-MEMORY-RELIABILITY_2026-08-27.md:25-36`; `COUNCIL-PREMIUM-GROK_2026-08-28.md:181`; `runtime-claude.md` generated 51 / live 74; `AGENTS.md` G-26/G-36 and RAM note.
- **value x effort:** HIGH × ZERO (don't-build). The win is refusing the clone.
- **NATIVE-vs-BUILD:** NATIVE policy already exists. BUILD of 51-everywhere is the anti-pattern.

### 2. RAM-BUDGET-FORBIDS-51-STDIO

- **name:** RAM-BUDGET-FORBIDS-51-STDIO
- **what:** Control-plane idle budget is **6 GiB** total and **512 MiB** per server. Those numbers are validated as constants; other totals fail `validate_registry`. 51 × 512 MiB = 25.5 GiB idle if every server were a local process — over the 6 GiB cap and most of the 32 GB box. Floor(6 GiB / 512 MiB) = **12** concurrent stdio servers at the default cap, for the **whole** estate idle budget, not per runtime.
- **why-this-estate:** Claude's generated 51 is already a superset of that 12-slot stdio budget. Multiplying 51 across 6+ CLIs would multiply process trees (measured once: 27 dead-parented MCP orphans). HTTP hubs still cost **tool-schema RAM in the client** (Cursor OOM at 154 tools; Hermes 529 tools on 17 hubs).
- **how:** Keep stdio RE on Claude (opt-in / titled RE), HTTP hubs on Hermes, G-6 on Cursor, 4 on Codex. Do not "share the 51" as names if the processes would be stdio.
- **source:** `mcp_control_plane.py:19-20,185-187`; `agents.json:15-35`; `HERMES-HARMONIZATION_2026-09-03.md:50-56`; `merge_generated_cursor_mcp.py:123-127`. Arithmetic is policy-math from those constants, not a live 51-process RSS sample. I have **not** measured 51 concurrent MCP RSS on this box.
- **value x effort:** HIGH × ZERO. The cap is already code.
- **NATIVE-vs-BUILD:** NATIVE (`validate_registry`). Do not BUILD a bypass.

### 3. POLICY-PARITY-ALREADY-SHIPPED

- **name:** POLICY-PARITY-ALREADY-SHIPPED
- **what:** "Parity" on this estate already means: same **control plane**, same **skills vault**, same **BM writer**, declared **different MCP subsets**. Cursor 6 vs Codex 4 vs Hermes 17 vs Claude 51 is intentional, not drift to "fix" by copying 51.
- **why-this-estate:** Universal harness share (HARD) is skills+rules from `.agents`, not identical MCP maps. Scorecard 27.08 already recorded Cursor 6+31 parked, Codex 4/40, Grok hand-maintained. Cursor merge docstring: G-6 keep-list; without `--attach-all-safe` it writes only that set. Hermes G-1: HTTP only, no stdio. Grok parked 27.08: keepers BM+agent-mail, strip CLI to HTTP hubs (G-11/G-99).
- **how:** Document the subset table above as the MCP contract. Sync continues to merge Claude/Codex/Cursor/ZCode/Hermes as today. Grok stays out of `VALID_TARGETS` until a **keepers-only** writer exists (optional; not required for this REC).
- **source:** `CROSS-RUNTIME-SCORECARD_2026-08-27.md:9-32`; `merge_generated_cursor_mcp.py:123-147,186` via `sync_shared_state.ps1`; `mcp-grok-parked_2026-08-27.toml:1-8`; `HERMES-HARMONIZATION_2026-09-03.md:9-18`; `agents.json` per-server `targets`.
- **value x effort:** HIGH × LOW (write the table into the parity folder; do not add a 51-merge).
- **NATIVE-vs-BUILD:** NATIVE (`targets[]`, keep-lists, parked files). Optional BUILD = read-only drift-check (scorecard already recommended this 27.08; still unbuilt). That drift-check is **not** `merge_generated_grok_mcp.py`.

### 4. GROK-MERGE-TRAP

- **name:** GROK-MERGE-TRAP
- **what:** DEDUP PLANNED-unbuilt = `grok` as `VALID_TARGET` + `merge_generated_grok_mcp.py`. Building that as "attach Claude's 51" would be the fastest way to implement rejected surface-parity. Live Grok already drifted to **22** TOML servers + **34** plugins against G-11/G-99 keepers. A naive merge would either (a) freeze the bloated 22, or (b) dump 51 into `config.toml`.
- **why-this-estate:** Grok is **not** in `VALID_TARGETS`; `agents.json` has **zero** `grok` target strings; `sync_shared_state.ps1` has **zero** grok merge hits; `merge_generated_grok_mcp.py` **is not a file**. Hermes G-4 (03.09): Grok TUI stays parked; unpark procedure is review parked TOML, convert to hub URLs, **then** add grok target — not clone stdio. Grok truncates rules files at 10,000 chars; MCP is hand-maintained. This session's BM handshake failed because Grok still uses `:8765` while SSOT is `:18765`.
- **how:** If a Grok merge is ever built, it must write **only** declared keepers: `basic-memory` HTTP `http://127.0.0.1:18765/mcp` and `agent-mail` HTTP `:18812`, both enabled. It must not attach Claude's 51, Cursor G-6 extras (chrome-devtools/playwright), or the parked stdio catalog. Prefer a **NATIVE** two-URL edit now over BUILD. A keepers-only merge is MEDIUM effort and only worth it if hand-edits keep re-expanding the 22.
- **source:** `mcp_control_plane.py:15`; `inventory.md:66-70`; `runtime-grok.md`; `mcp-grok-parked_2026-08-27.toml:1-8`; `HERMES-HARMONIZATION_2026-09-03.md:16-18`; `memory-audit.md:49-65`; `sync_shared_state.ps1` merge list (claude/codex/cursor/zcode/hermes only).
- **value x effort:** HIGH × LOW for the URL retarget (NATIVE). MEDIUM × MEDIUM for a keepers-only merge (BUILD, optional). NEGATIVE × HIGH for a 51-copy merge (REJECT).
- **NATIVE-vs-BUILD:** NATIVE fix first. BUILD only as keepers-only writer + drift-check. Do not BUILD Claude-clone.

### 5. BM-EVERYWHERE-IS-THE-REAL-PARITY

- **name:** BM-EVERYWHERE-IS-THE-REAL-PARITY
- **what:** The only MCP that must work on every in-use runtime is basic-memory (G-81 sole writer) plus agent-mail as the peer rail. That is currently **false for Grok**. Claude/Codex/Cursor/ZCode/Hermes live maps use `:18765` / `:18812`. Grok TOML still uses `:8765` / `:8812` with agent-mail `enabled=false`. Shared daemon is UP on `:18765` (memory-audit TCP+GET+initialize). `:8765` is closed. Inventory.md `BM-DOWN` / "Grok BM :18765" is a **detector failure** (probes 8765 then names 18765).
- **why-this-estate:** This Grok session has no `basic-memory` tools. Hybrid `search_notes` cannot run here. Policy-parity without working BM is a hollow contract. Cursor needed a stdio SSE/session shim (`bm_cursor_http_session.py`) for the same daemon; Grok is raw `type=http`. URL retarget is sufficient for the closed-port failure (~99%). A Grok streamable-http/session shim is a **second** failure class (~70% if URL-only still red) — do not start that BUILD until the URL is fixed and re-probed.
- **how:** Edit `~\.grok\config.toml` keepers to SSOT ports; enable agent-mail; do **not** restart BM/agent-mail daemons from this finding. Do not rotate anything.
- **source:** `memory-contract.md:10-11`; `memory-audit.md` (daemon UP `:18765`, Grok URL `:8765`); `runtime-grok.md:35-41`; `inventory.json` `memory.grok.url`; rail migrate note in `memory-audit.md:23`; Cursor shim `merge_generated_cursor_mcp.py` + `agents.json` `x_cursor.stdio_bridge`.
- **value x effort:** HIGH × LOW (two URLs + enable flag). Highest value×effort item in this lens.
- **NATIVE-vs-BUILD:** NATIVE config. Cursor shim already BUILT. Grok shim is **not** in DEDUP BUILT; only build after URL fix fails.

### 6. CURSOR-13-NATURAL-EXPERIMENT

- **name:** CURSOR-13-NATURAL-EXPERIMENT
- **what:** Same-day Cursor `mcp.json.bak-*` held **13** servers (G-6 + 7 Hermes CyberStrike hubs). Live is **6**. Default merge (`sync_shared_state.ps1` `--write` without `--attach-all-safe`) cleared the 7. Prompt "Cursor 13" is **not live**. hexstrike retired from Cursor because 154-tool dump OOMs (G-15/G-18). Parked-31/32 is a rollback catalog, not a load path.
- **why-this-estate:** This is the empirical test of "just add the hubs everywhere." It lasted hours, then policy put G-6 back. `--attach-all-safe` would project Claude-safe registry defs into Cursor and re-risk the OOM (retired-set blocks hexstrike, not every fat schema).
- **how:** Keep SAFE_DEFAULT. Do not treat bak-13 as a target state. Do not add Hermes-only hubs to Cursor by hand again.
- **source:** `runtime-cursor.md:15-30`; `merge_generated_cursor_mcp.py:120-147`; `mcp-cursor-parked-31.json` `_comment`; `sync_shared_state.ps1:185-186`.
- **value x effort:** HIGH × ZERO (already reverted). Re-opening attach-all-safe is NEGATIVE value.
- **NATIVE-vs-BUILD:** NATIVE merge policy. `--attach-all-safe` is a built gated mode — leave it gated.

### 7. SILENT-SECOND-CONFIGS

- **name:** SILENT-SECOND-CONFIGS
- **what:** Policy-parity dies if a second definition surface loads undeclared servers. Grok: TOML vs 34 plugins / 19 plugin `.mcp.json` (name ∩ with TOML empty; firecrawl vs firecrawl-hub). Claude: merge `.claude.json` vs `~/.mcp.json` (21) vs `disabledMcpServers` (131 names; 55/74 live keys listed). Codex/ZCode: plugin-cache `.mcp.json` beside merge maps. Cursor plugins currently all `enabled: false` (not a second **loaded** map today).
- **why-this-estate:** Grok's 22+34 is how keepers became a fleet without a merge script. Claude UI-on ≈19 vs generated 51 vs live 74 — three numbers, one product. "51 everywhere" would ignore the disable-array that already shrinks Claude.
- **how:** Declare skip-sets that match live plugin state (Cursor `tavily` skip is stale vs `enabled: false`). Do not load `~/.mcp.json` into other runtimes. Grok plugin MCP stays a second surface until owner disables or declares it.
- **source:** `dual-config.md` table + intra-file duals; `runtime-grok.md:15-33`; `runtime-claude.md:39-44`; `runtime-cursor.md:32-33`.
- **value x effort:** MEDIUM × LOW (declare; do not build a unifier).
- **NATIVE-vs-BUILD:** NATIVE disable/skip. BUILD of a cross-runtime second-config merger is REJECTED (would be a second control plane).

### 8. CLAUDE-51-IS-NOT-THE-DAILY-SET

- **name:** CLAUDE-51-IS-NOT-THE-DAILY-SET
- **what:** Even Claude does not run 51 daily. Generated 51 ⊂ live 74, but `disabledMcpServers` leaves UI-on ≈ **19**. Council 28.08 already said: shrink Claude daily MCP; keep HTTP rails; make RE stdio opt-in for titled sessions. Cursor's 6-server allowlist "already did the analogous cut; Claude's bridge did not."
- **why-this-estate:** Using 51 as the parity target copies a **registry width**, not the live daily surface. Copying it to Grok/Cursor would widen those runtimes past Claude's own UI-on set.
- **how:** If any "parity" number is needed, use **keepers + declared extras**, not generated-51. Claude RE stdio stays Claude-scoped.
- **source:** `runtime-claude.md:13-44`; `COUNCIL-PREMIUM-GROK_2026-08-28.md:181`; generated name list in `runtime-claude.md:27`.
- **value x effort:** HIGH × LOW (stop using 51 as the north star).
- **NATIVE-vs-BUILD:** NATIVE disable-array already shrinks Claude. Do not BUILD a 51-expander.

---

## Policy-parity vs surface-parity (choice)

| | Surface-parity | Policy-parity (REC) |
|---|---|---|
| Definition | Same 51 server names attached in every runtime | Declared subsets; same BM/agent-mail rails; no silent maps |
| RAM | 51×N process/schema cost; fights 6 GiB cap | Subsets already sized (6 / 4 / 17 / 2 / keepers) |
| Matches locks | Conflicts G-6, G-11/G-99, G-1, G-15, G-4 Grok-parked | Honors them |
| Sync | Would require grok+goose+agy as Claude-clones | Existing merges + optional keepers-only Grok writer |
| BM | Still broken on Grok if only names are copied to wrong ports | Fixes the actual outage |
| DEDUP | Re-proposes PLANNED-unbuilt as 51-copy | Leaves PLANNED-unbuilt narrowed to keepers-only or unbuilt |

Pick: **policy-parity**.

---

## DEDUP (do not re-propose)

- **BUILT:** `sync_shared_state.ps1` + claude/codex/cursor/zcode merges + hermes deploy + Cursor `stdio_bridge` + `mcp-cursor-parked-31.json` + `mcp-grok-parked_2026-08-27.toml`.
- **PLANNED-unbuilt:** grok `VALID_TARGET` + `merge_generated_grok_mcp.py` — **narrow to keepers-only or leave unbuilt**. Not a 51-copy.
- **ABSORBED:** AgentBridge retired.
- **REJECTED:** 2nd orchestration runtime; Mem0/Graphiti; Cursor BYOK; OpenRouter MCP; **surface-parity 51-everywhere** (this unit).

---

## What this unit did not do

- Did not edit `~\.grok\config.toml` (parent/owner action; this unit is gem-hunt).
- Did not restart BM / agent-mail / bind `:18765`/`:18812`/`:8317`.
- Did not measure live RSS of 51 MCP processes (not running).
- Did not re-probe TCP (used memory-audit + inventory TCP claims; memory-audit supersedes inventory BM-DOWN).

UNIT-COMPLETE: gem-wildcard
disk-verified: this file
confidence: almost certain (~95%) that 51-everywhere is undesirable; ~99% that Grok BM is on the wrong port vs SSOT.
