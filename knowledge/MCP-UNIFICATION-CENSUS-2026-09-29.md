# MCP Unification Census — 2026-09-29 (post-consolidation)

**Mandate (owner):** no more broken MCPs; everything in the hub; discoverable like skills.
**Executed this session:** `.mcp.json` project-scope injection path CLOSED (renamed `.retired-20260929`);
7 unique entries merged into user scope (`~/.claude.json` now 37 mcpServers, 92 keys intact);
backups: both files `.bak-consolidated-20260929`. Discovery = ToolSearch deferred layer (native, is the "skills-like" UX).

## Classification (live-verified 2026-09-29)
**HEALTHY-HTTP-REMOTE:** brightdata, context7, figma, github(copilot), linear, notion, web-reader, web-search-prime, zread (z.ai)
**HEALTHY-LOCAL-BAND 311xx (400=live):** github-security :31110, cve-mcp :31111, osint :31112, firecrawl :31114, hacktricks :31115, metasploit :31116, nuclei :31117
**FIXED-TONIGHT:** basic-memory :18765 (3-layer remnant stack cleared; tools/list 21 verified)
**REVIVED-TONIGHT:** biomni broker fleet (3 accounts, Chrome CDP 9222-24 off-screen now, brokers 18787-89)
**DEAD BACKEND (start procedure needed):** hexstrike-ai :31113, cloud-audit :31118, semgrep :31119 (band fronts live, backends down?)
**AUTH-BROKEN:** huggingface (401 token — OWNER decision, never rotate per §9)
**BACKEND-ON-DEMAND (by design, document start):** sliver/sliver-full (Sliver server), burp (Burp Suite app), jupyter (uvx timeout — investigate), dbx-ai (python child)
**LEGACY/DECISION:** biomni :7870 standalone front (superseded by cloud-hub-first — locate cloud-hub wiring); McpHub SSE :24680 (empty index, children timeout — RETIRE recommendation, superseded by direct+ToolSearch; codex has native mcp-server mount)
**REGRESSION-RISK (owner challenge 2026-09-29, verdict DOWNGRADED):** McpHub uniquely fronts ~40 backends ABSENT from the 37 user-scope entries (angr, ghidra-mcp, ida-pro-mcp, docker, kaggle, apktool, binary-ninja, cheatengine, biomcp, scholar-side...). Removing it WITHOUT remounting those = losing the RE/research backend lane. Decision is now CONDITIONAL: restart-and-repair McpHub vs retire+remount-children — compare at ratification with the daemon freshly started (2026-09-20 memory: it was RESTORED once before, root cause was killable).

**LOST:** MCP-audit scoreboard.json (D1-D25) — file gone; superseded by this census.

## Self-inflicted incidents tonight (both ledger'd, both repaired)
1. Needle collision: 'biomni' substring mass-kill took out live brokers → idempotent autostart repaired. Rule: enumerate PIDs, kill individually.
2. Partial-load/partial-write: merge script rewrote .claude.json with ONLY mcpServers → restored from pre-edit backup, redone as full-dict modify. Rule: never rewrite a config you only partially loaded.

## Staged for owner (not executed)
- McpHub retirement (config edit, next-session — mid-session config edits invalidate caches)
- hexstrike/cloud-audit/semgrep backend starts
- Ubuntu reinstall-or-cutover (open loop 89a57973, by 2026-10-06)
- Full gem-hunt fan-out — G-99 RAM-gated (< 8 GB free tonight), run when PentAGI flow idles


RECALL: basic-memory search 'McpHub restore 2026-09-20' (restored once, killable root cause) + census lines 17-19 (regression-risk, lost scoreboard)
DEPS: McpHub fronts ~40 hub-only backends (angr ghidra ida docker kaggle apktool binary-ninja cheatengine biomcp scholar-stack) vs 37 user-scope entries — retire requires remount of all, else regression
