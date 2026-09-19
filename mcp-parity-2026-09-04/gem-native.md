# Gem-hunt `native` — enable vs build (Grok MCP parity)

Date: 2026-09-04. Lens: native capability. Unit: gem-native.
Goal: smallest durable MCP parity for Grok is a merge script + `grok` VALID_TARGET, not a new daemon.

Disk-verified this turn (read, not digest): inventory.md/json, mcp_control_plane.py, agents.json, sync_shared_state.ps1, merge_generated_{codex,cursor,claude,zcode}, deploy_hermes_mcp.py, ~/.grok/config.toml, ~/.grok/docs/user-guide/{07,08,09,13,26}, ~/.cursor/mcp.json, mcp-grok-parked_2026-08-27.toml, CROSS-RUNTIME-SCORECARD_2026-08-27.md, memory-contract.md.

No new daemon. No credential rotation. LITERAL-SECRET-PRESENT on live Grok `mcphub` header key `Authorization` (value not copied).

## Verdict

Skills/rules are already native-on. MCP parity is a **control-plane targeting gap**, not a missing runtime. Grok already speaks stdio/HTTP/SSE, `grok mcp enable/disable`, plugin MCP, and Claude/Cursor MCP compat loaders. `select_target_servers()` cannot emit `grok` until `VALID_TARGETS` includes it. Clone the Codex TOML merger; keep G-11/G-99 keepers as the safe-default; pin compat MCP off so Claude’s 51 do not dump into Grok.

`VALID_TARGETS` (mcp_control_plane.py:15): `frozenset({"claude", "codex", "zcode", "hermes"})`. Cursor is also not a target; its merge **mirrors `claude`**. Grok must not.

---

### 1. GROK-SKILLS-ALREADY-NATIVE
- **what:** `[paths] extra_skill_dirs` → `C:\Users\Prekzursil\.agents\skills`; `[paths] extra_rule_dirs` → `C:\Users\Prekzursil\.agents\rules`. `~/.grok/skills` empty; `default_skills_installs_purged = true`.
- **why-this-estate:** Universal harness share: one vault, no second copy.
- **how:** Leave the two `[paths]` keys. Do not materialize the vault into `~/.grok/skills`. Grok also walks `.agents/skills` cwd→repo-root natively (user-guide 08).
- **source:** live config.toml:285-286; user-guide 08-skills.md, 26-config-reference.md `paths.extra_*`; ~/.grok/AGENTS.md:14-19; scorecard 2026-08-27 Grok row.
- **value x effort:** already done / zero.
- **NATIVE-vs-BUILD:** **NATIVE ENABLE (done).** Not an MCP-parity build.

### 2. GROK-MCP-TRANSPORTS-NATIVE
- **what:** `[mcp_servers.<name>]` supports `command`/`args` stdio, `url` + `type` http/sse, `headers`, `env`, `enabled`, `startup_timeout_sec`, `bearer_token_env_var`, OAuth. CLI: `grok mcp add|enable|disable|list|doctor`. Docs: prefer `url` over `npx mcp-remote`.
- **why-this-estate:** Keepers and hubs are already HTTP. RAM cannot afford extra stdio trees.
- **how:** Render registry HTTP as `url`/`type=http`. Use `${VAR}` or native `bearer_token_env_var`. Do not add a Grok MCP daemon.
- **source:** user-guide 07-mcp-servers.md, 26-config-reference.md `mcp_servers.*`; live config.toml:307-420.
- **value x effort:** high / already present.
- **NATIVE-vs-BUILD:** **NATIVE.** Merge only *writes* these keys.

### 3. GROK-NOT-A-VALID-TARGET
- **what:** `VALID_TARGETS = frozenset({"claude", "codex", "zcode", "hermes"})`. `select_target_servers(config, target)` raises `unsupported target` otherwise. `agents.json` has **zero** `"grok"` strings. `basic-memory` and `agent-mail` targets are `codex, claude, zcode, hermes` only.
- **why-this-estate:** Without `grok` in VALID_TARGETS a merger cannot call the shared selector. Cursor’s workaround (`select_target_servers(..., "claude")`) would attach Claude’s 51 — RAM-hostile and against G-11/G-99.
- **how:** Add `"grok"` to VALID_TARGETS; tag keeper (and any later HTTP-hub) servers with `"grok"` in `targets`. Analog is Hermes (own target, HTTP subset), not Cursor (mirror Claude).
- **source:** mcp_control_plane.py:15, 386-409; agents.json basic-memory:763-768, agent-mail:1193-1198; grep grok in agents.json = none.
- **value x effort:** high / ~1 line + target tags.
- **NATIVE-vs-BUILD:** **BUILD (smallest durable).** Required so the native TOML surface is driven by SSOT.

### 4. GROK-NO-MERGE-SCRIPT
- **what:** No `merge_generated_grok_mcp.py`. `sync_shared_state.ps1` runs claude/codex/cursor/zcode merges + hermes deploy. Inventory merge-present: grok=NO.
- **why-this-estate:** Live Grok MCP is hand-edited; drifted from G-11/G-99 and from agents.json URLs.
- **how:** Clone `merge_generated_codex_mcp.py` (same `[mcp_servers.*]` TOML, preserve non-MCP). Safe-default keepers like Cursor G-6, not Claude-all. Skip plugin-provided names. `--check` drift. Wire into sync_shared_state after zcode. Park non-keepers in existing `mcp-grok-parked_2026-08-27.toml`.
- **source:** inventory.md Merge scripts; sync_shared_state.ps1:63-66, 195-210; merge_generated_codex_mcp.py; deploy_hermes_mcp.py HTTP-only G-1.
- **value x effort:** high / small (Codex clone + keep-list).
- **NATIVE-vs-BUILD:** **BUILD.** The only unbuilt DEDUP-SET item. Not a daemon.

### 5. GROK-COMPAT-MCP-DEFAULT-ON (do not use as parity)
- **what:** `[compat.claude] mcps` and `[compat.cursor] mcps` default **yes**. Live config has no `[compat]` table, so Grok already scans Claude MCP + `~/.cursor/mcp.json`. Priority: config.toml > Claude > Cursor > `.mcp.json`. `[claude_compat] imported = true` skips `~/.mcp.json`.
- **why-this-estate:** Compat-on would *add* every Claude name not already in Grok TOML (chrome-devtools, playwright, context7, firecrawl, …) on top of 22 hand entries. RAM. Cursor G-6 would lose to Grok’s same-name blocks (wrong BM port wins).
- **how:** **ENABLE:** set `[compat.claude] mcps = false` and `[compat.cursor] mcps = false` so the grok-target merge is the only MCP SSOT. Do not “fix parity” by turning Claude compat on.
- **source:** user-guide 07 Compatibility table; 26-config-reference.md `compat.*.mcps`; config.toml:422-423 `[claude_compat] imported = true`; no `[compat]` keys in live TOML.
- **value x effort:** high / one table, two bools.
- **NATIVE-vs-BUILD:** **NATIVE ENABLE (pin off).** Using the loader as a substitute for a grok target is rejected.

### 6. GROK-KEEPERS-PORT-AND-ENABLE-DRIFT
- **what:** G-11/G-99 keepers = basic-memory + agent-mail. Live Grok: BM `url = http://127.0.0.1:8765/mcp` enabled; agent-mail `http://127.0.0.1:8812/mcp` **enabled=false** and listed in `disabled_mcp_servers`. SSOT: BM `http://127.0.0.1:18765/mcp`, agent-mail `http://127.0.0.1:18812/mcp/`. This session’s connected MCP list has **neither** keeper. `~/.grok/AGENTS.md:155` still says 8765.
- **why-this-estate:** Memory-contract HARD transport; estate lock “nothing binds :18765/:18812/:18317 except owners”. Retired 8765/8812 are closed per inventory TCP. Keepers are configured at dead ports and/or disabled.
- **how:** **ENABLE:** retarget URLs to 18765/18812; `grok mcp enable agent-mail`; do **not** restart BM/agent-mail or bind 8765/8812. Merge script must emit SSOT URLs so this cannot drift.
- **source:** config.toml:307-315, disabled_mcp_servers includes agent-mail; agents.json URLs; memory-contract.md:10-11, 77; Cursor mcp.json agent-mail 18812 + BM 18765; inventory TCP :8765/:8812 closed.
- **value x effort:** critical / minutes once merge exists; one-shot enable meanwhile.
- **NATIVE-vs-BUILD:** **NATIVE ENABLE** of existing HTTP daemons. Merge makes it durable.

### 7. GROK-STREAMABLE-HTTP-SESSION (no Grok BM shim)
- **what:** Cursor BM uses `x_cursor.stdio_bridge` → `bm_cursor_http_session.py --stdio --url http://127.0.0.1:18765/mcp`. Grok docs: native HTTP/SSE + `headers = { "x-mcp-session-id" = "{{session_id}}" }`. Inventory “Grok BM handshake failed” was against the wrong/retired port story, not proof Grok needs a new shim.
- **why-this-estate:** Cursor’s HTTP client does not heal stale BM sessions; Grok claims native streamable HTTP. Extra Python stdio per Grok session costs RAM.
- **how:** First: native `url` 18765 ± `{{session_id}}`. Only reuse `bm_cursor_http_session.py` if `grok mcp doctor basic-memory` fails on 18765 (two-signal). Do not write `x_grok.stdio_bridge` unless that doctor fails.
- **source:** user-guide 07 Streamable HTTP; agents.json x_cursor.stdio_bridge:790-797; Cursor mcp.json:5-13; inventory GROK-BM-RAW-HTTP.
- **value x effort:** high / zero if HTTP works; small reuse if not.
- **NATIVE-vs-BUILD:** **NATIVE first.** Reuse existing Cursor shim only if doctor falsifies HTTP. No new daemon.

### 8. GROK-PLUGIN-MCP-SECOND-SURFACE
- **what:** Marketplace plugins are a second MCP loader (`grok plugin enable/disable`). Live `[plugins].enabled` includes chrome-devtools-mcp, context7, firecrawl, exa, tavily, cloudflare, … This session connected `context7`, `firecrawl`, `cloudflare-docs`, `google_drive`, `tasks` which are **not** in `[mcp_servers]`. AgentBridge plugin already disabled (`user/0aaa06d9/agentbridge`).
- **why-this-estate:** Duplicate Firecrawl (plugin hosted vs `firecrawl-hub` :31414). Claude/Cursor merges already skip plugin-provided names.
- **how:** **ENABLE:** `grok plugin disable` on MCP-providing plugins that duplicate registry/hubs. Merger `plugin_provided=` must include Grok plugin MCP names (same pattern as CLAUDE_PLUGIN_PROVIDED_SERVERS / CURSOR_PLUGIN_PROVIDED_SERVERS).
- **source:** config.toml [plugins]; user-guide 09-plugins.md; inventory 34 marketplace plugins; this session MCP list vs config.toml names.
- **value x effort:** medium / disable + skip-list.
- **NATIVE-vs-BUILD:** **NATIVE DEDUP.** Merge skip-list is a few frozen names, not a new runtime.

### 9. GROK-POLICY-REGRESSION-22-VS-2
- **what:** Parked 2026-08-27 catalog says keepers left in config were BM+agent-mail. Live `[mcp_servers]` has 22 names (20 extra vs keepers), mostly local HTTP hubs + remote OAuth. `search-hub` is stdio `python.exe hub.py` (not HTTP).
- **why-this-estate:** G-11/G-99 strip Grok to HTTP hubs keepers; RAM. Hermes already owns the HTTP-hub set (`hermes` target, 17 enabled). Grok should not also stdio-spawn search-hub.
- **how:** Safe-default attach {basic-memory, agent-mail} only. Park the rest (file already exists). Prefer existing hub HTTP URLs if owner later expands Grok; never spawn a second hub process. `grok mcp disable` for the 20 extras is the one-shot ENABLE.
- **source:** mcp-grok-parked_2026-08-27.toml header; live config.toml 22 sections; inventory GROK-POLICY-REGRESSION; deploy_hermes_mcp.py ALLOWED_TRANSPORTS={"url"}.
- **value x effort:** high / disable now; merge prevents resurrection.
- **NATIVE-vs-BUILD:** **NATIVE disable + BUILD keep-list.** No new hub.

### 10. GROK-BUILTIN-MEMORY-STAY-OFF
- **what:** Grok `[memory]` experimental store under `~/.grok/memory/`. Default disabled. Live config.toml has no `[memory]` and no GROK_MEMORY.
- **why-this-estate:** G-81 basic-memory is the sole semantic writer. Parallel Grok memory is a second store (same class as ZCODE-SECOND-MEMORY).
- **how:** Leave off. Do not `GROK_MEMORY=1`.
- **source:** user-guide 13-memory.md; grep `[memory]` in config.toml = none; memory-contract.md writer lock.
- **value x effort:** hygiene / zero.
- **NATIVE-vs-BUILD:** **NATIVE leave-disabled.** Rejected: Mem0/Graphiti/Grok-memory-on.

### 11. GROK-MCPHUB-LITERAL-SECRET
- **what:** `[mcp_servers.mcphub.headers] Authorization` is a literal bearer, not `${VAR}`. Grok natively expands `${VAR}` and has `bearer_token_env_var`.
- **why-this-estate:** NEVER commit/paste live secrets; NEVER-ROTATE. Inventory redacts; this audit does not copy the value.
- **how:** Replace with env ref (ENABLE). Merger must refuse literals (control-plane already has LITERAL_SECRET_RE). Report blast radius only; do not rotate.
- **source:** config.toml:358-364; user-guide 07 env expansion; mcp_control_plane.py LITERAL_SECRET_RE.
- **value x effort:** high / one header.
- **NATIVE-vs-BUILD:** **NATIVE** interpolation. LITERAL-SECRET-PRESENT key=`Authorization` (mcphub).

### 12. GROK-DISABLED-LIST-VS-ENABLED-FLAG
- **what:** Top-level `disabled_mcp_servers` includes huggingface, agent-mail, figma, notion, linear, … while `[mcp_servers.huggingface] enabled = true` (and notion/linear enabled=true). Dual native disable channels.
- **why-this-estate:** Merge that only writes `enabled=` can be overridden by `disabled_mcp_servers` (or vice versa). Doctor/list will lie.
- **how:** Merger should own both: keep-list enabled=true and **absent** from `disabled_mcp_servers`; extras in the disabled list. `grok mcp enable/disable` is the native CLI for the same list.
- **source:** config.toml:1-18 vs :321-331, :342-344; user-guide 07 enable/disable persist rules.
- **value x effort:** medium / include in merge renderer.
- **NATIVE-vs-BUILD:** **NATIVE dual-knob**; merge must write both.

### 13. CURSOR-G6-ALREADY-MERGED (not Grok’s job)
- **what:** Live `~/.cursor/mcp.json` has exactly 6: agent-mail, basic-memory (stdio_bridge), chrome-devtools, context7, firecrawl, playwright. Matches CURSOR_ENABLED_SERVERS / G-6. Parked-31 is the defer catalog. Cursor is **not** in VALID_TARGETS; merge selects `claude` then filters to G-6.
- **why-this-estate:** Prompt claim “Cursor 13” is **not** disk-verified; inventory.md and mcp.json both say 6.
- **how:** Leave Cursor merge. Do not add cursor to VALID_TARGETS in this unit.
- **source:** ~/.cursor/mcp.json; merge_generated_cursor_mcp.py:129-147, 375-378; mcp-cursor-parked-31.json header.
- **value x effort:** n/a (done).
- **NATIVE-vs-BUILD:** **already BUILT** (cursor merge). Out of Grok gem-native scope except as the keep-list pattern to copy.

### 14. REJECTED-NOT-THIS-LENS
- Second orchestration runtime; Mem0/Graphiti/LynxMCP/CORE; Cursor BYOK; OpenRouter MCP; Grok-as-Claude-mirror; new BM/agent-mail/mcphub daemon; restarting :18765/:18812/:18317.
- ABSORBED: AgentBridge (plugin disabled).
- PLANNED-unbuilt (only): `grok` VALID_TARGET + `merge_generated_grok_mcp.py`.

## Enable vs build (ordered)

1. **ENABLE now (no code):** retarget Grok BM/agent-mail URLs; `grok mcp enable agent-mail`; `grok mcp disable` extras; `[compat.claude/cursor] mcps=false`; plugin-disable duplicate MCP; `${VAR}` for mcphub; leave Grok `[memory]` off.
2. **BUILD (durable, small):** `VALID_TARGETS += grok`; tag keepers; `merge_generated_grok_mcp.py` from Codex TOML merger + Cursor-style safe-default; hook `sync_shared_state.ps1`; `--check` in inventory.
3. **Do not build:** any new MCP daemon, Grok stdio BM proxy (unless doctor fails), vault copy into `~/.grok/skills`.

UNIT-COMPLETE: gem-native
