# Codex runtime MCP lens — 2026-09-04

**UNIT-COMPLETE: runtime-codex**
Receipt: this file. Inventory claims re-read, then live/generated/merge/registry re-read.

## Surface counts
- Registry (`agents.json`): **4 enabled / 4 targeted**. Names: agent-mail, apify, basic-memory, github.
- Generated view (`.agents/generated/codex.config.toml`): **4** (same names; MCP-only snapshot, not a live Codex home).
- Live (`~/.codex/config.toml`): **7 names**, **6 enabled**, **1 disabled** (cua_repl).
- Split: **4 registry-managed** vs **3 Codex-local preserved** (node_repl, cua_repl, mcphub).

## Registry-managed vs Codex-local
Registry-managed (merge **replaces** these). Live 997-1015 matches generated 1-16:
- agent-mail HTTP `http://127.0.0.1:18812/mcp/` enabled
- apify HTTP `https://mcp.apify.com/` enabled; bearer_token_env_var=APIFY_TOKEN
- basic-memory HTTP `http://127.0.0.1:18765/mcp` enabled
- github HTTP `https://api.githubcopilot.com/mcp` enabled; bearer_token_env_var=GITHUB_MCP_PAT

Codex-local preserved (merge **keeps** names not in agents.json servers union {memory, codex_consult}):
- node_repl stdio, no enabled key -> inventory default true. Bundled cua_node node_repl.exe. .env subblock kept.
- cua_repl stdio enabled=false. WindowsApps ChatGPT.exe.
- mcphub stdio cmd+npx mcp-remote to `http://127.0.0.1:24680/sse` enabled=true. LITERAL-SECRET-PRESENT key=Authorization (bearer in args, not env). Inventory TCP :24680 open.

Grep of agents.json for node_repl|cua_repl|mcphub: no matches (second signal). Retired memory/codex_consult are not in live mcp_servers.

## basic-memory HTTP?
**Yes.** Registry transport=http url `:18765/mcp`. Live and generated both `url = "http://127.0.0.1:18765/mcp"`. Matches memory-contract HARD (HTTP only, never stdio). Not Cursor stdio shim. Inventory BM-DOWN (:18765 closed) is daemon state; Codex config is still HTTP.

## second-config
**No** live second Codex MCP config. Native integrations.enabled=[] (sync would otherwise emit a second generated surface). Merge --write targets only `~/.codex/config.toml`. Generated TOML is reference-only (publish_reference_views.py). `.codex-vscode/config.toml` does not exist. Profile tomls (cursor/balanced/max) have 0 mcp_servers. `.codex/mcp-configs/mcp-servers.json` is a YOUR_*_HERE template (includes retired stdio memory), not the merge target.

## memory path
Canonical MCP: `http://127.0.0.1:18765/mcp`. Parallel on-disk store: `C:\Users\Prekzursil\.codex\memories\` (MEMORY.md read) plus memories_1.sqlite and memory.jsonl. Second writer vs G-81 (same class as ZCODE-SECOND-MEMORY).

## vs 2026-08-27
- Scorecard Codex MCP: 4/40 then; still 4 registry targets (denom now 68). No registry-count regression.
- Sync then: claude+codex+cursor; now also zcode+hermes; Codex still merged.
- Live extras (node_repl/cua_repl/mcphub) are by-design local preserve. Scorecard did not list live Codex MCP names, so not a proven 08-27 regression.
- New this lens: hardcoded mcphub Authorization; parallel `~/.codex/memories/`.

## Evidence (file:line)
- mcp_control_plane.py:15 VALID_TARGETS includes codex (not grok).
- agents.json:40-47 apify http+codex; :493-500 github; :763-771 basic-memory http :18765/mcp; :1193-1200 agent-mail http :18812.
- generated/codex.config.toml:1-16 four HTTP blocks.
- ~/.codex/config.toml:131-136 node_repl; :987-995 mcphub+cua_repl; :997-1015 managed four.
- merge_generated_codex_mcp.py:23 RETIRED; :74 select_target_servers(codex); :220-234 preserve-if-not-in-registry.
- sync_shared_state.ps1:63,71,175-180 live merge --write; native second surface disabled.
- memory-contract.md:10-11 BM HTTP-only.
- CROSS-RUNTIME-SCORECARD_2026-08-27.md:11,27 4/40 + Codex in sync.
- inventory.md:13,36; inventory.json:89-94,559-591.
