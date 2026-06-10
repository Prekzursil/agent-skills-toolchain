# Unified, Cross-AI MCP Architecture — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design); pending Plan Review gate → implementation
**Scope:** Spec 1 of a 3-spec program (see §10 Roadmap)
**Author context:** Windows 11 power user running Claude Code, Codex CLI, and Antigravity, with ~40 MCP servers spread across 5 config layers and a parallel `mcp-funnel` aggregator.

---

## 1. Problem & Motivation

Diagnosed this session (process forensics + source reading + official docs + real-world precedent):

- **Per-session fleet duplication.** Claude Code spawns its *own* copy of every stdio MCP server per session (CC issue [#28860](https://github.com/anthropics/claude-code/issues/28860)). ~52 servers loaded when launching from the home dir (21 user-scope ∪ 39 home-`.mcp.json` − 8 overlap). Two sessions ≈ **8.4 GB** of MCP child working set; semgrep Pro engine alone ≈ **920 MB resident *per session*** (plugin layer, escalates to `osemgrep-pro` since the 2026-06-05 semgrep 1.165 update).
- **`mcp-funnel` does not help RAM.** Source read (`MCPProxy.initialize` → `connectToTargetServers` → `StdioClientTransport.start` → `spawn`) proves it **eager-spawns ALL backends at startup**; `enableDynamicDiscovery` only hides *tool schemas* (saves context tokens, not RAM). Maintainer issue [#95](https://github.com/chris-schra/mcp-funnel/issues/95) confirms ("149 instances, 91 GB"). Funnel is also **stdio-only as a server** → cannot be a shared HTTP daemon. Confidence: HIGH.
- **Native Tool Search already replaces funnel's token role.** CC v2.1.121+ defers MCP tool schemas by default ([docs](https://code.claude.com/docs/en/mcp.md)). Funnel is now redundant overhead.
- **Five config categories** (Project / Local / User / Plugin / claude.ai) with cross-layer duplicates (`context7`, `github`/`github_cli`, `binary-ninja`, `tavily`, browser tools ×4). User wants **one local category** (+ claude.ai remotes) and **cross-AI** availability (Claude, Codex, Antigravity).

**Documented precedent for the fix:** a shared HTTP MCP daemon cut **172 → 33 processes, ~3 GB → <1 GB** across 7 sessions ([shyamverma.com](https://shyamverma.com/shared-mcp-servers-claude-code)). Official CC docs confirm **stdio = per-session child process (not lazy, no defer toggle); HTTP/SSE = a connection, not duplicated per session.**

## 2. Goal & Success Criteria

One shared, lazy, low-overhead MCP backend fleet reachable by **all** local AIs, collapsing the 5 Claude categories into **one logical layer + claude.ai remotes**.

- **G1** A fresh session of Claude / Codex / Antigravity sees all intended tools.
- **G2** Steady-state MCP RAM drops from ~8 GB → ~1–1.5 GB.
- **G3** ralph headless loops (`--setting-sources project,local`) still reach their tools.
- **G4** No destruction of the user's enable/disable curation; every change reversible (timestamped backups, one-command rollback). *(Honors the load-bearing curation rule.)*
- **G5** Codex `tools.namespace 'web' collides` error resolved as part of cross-AI registration.

## 3. Architecture

```
                 ┌──────────────────────────────┐
 Claude Code ───▶│   1mcp gateway daemon         │  lazy-spawn, shared:
 Codex CLI   ───▶│   http://127.0.0.1:<PORT>/mcp │──▶ backend MCP procs
 Antigravity ───▶│   tag presets = "loadouts"    │   (started on 1st use,
 (any MCP    ───▶│   per-backend namespacing      │    ONE set for ALL AIs)
  client)        └──────────────────────────────┘
   untouched:  claude.ai remote connectors (0 local RAM)
   kept LOCAL (stateful, per-client):  RE fleet + playwright + codex-bridge
```

**Gateway technology:** `1mcp` (`@1mcp/agent` v0.32.2) — the only option offering lazy-spawn **and** cross-session sharing **and** per-session tag filtering (matches the literal requirement "available at all times via lazy loading without overhead"). Pure Node (no OS restriction in manifest). **Risk:** Windows support unverified → mitigated by P0 spike + fallback to `sparfenyuk/mcp-proxy` (`uv tool install mcp-proxy`; proven on Windows; keeps sharing, loses lazy-spawn).

## 4. Server Disposition Map (dedup + merge core)

| Bucket | Servers | Rationale |
|---|---|---|
| **→ Gateway** (lazy, shared, all-AI) | tooluniverse, scholarly-access, academia, rdkit, schrodinger, huggingface, firecrawl, scrapegraph, apify, markitdown, pdf-reader, excel, ocr, repomix, **github** (merged), mcp-graphql, linear, notion, figma, codacy, codecov, deepsource, deepscan, qlty, sonarqube, sentry, semgrep (OSS), docker, postgres, digitalocean, browserstack, basic-memory, tiktok, insta-mcp, fb-messenger | Stateless request/response → safe to share; lazy = free when unused |
| **Stay LOCAL** (stateful, not shared) | ida-pro-mcp, ghidra-mcp, binary-ninja-mcp, frida-mcp, cheatengine, hexstrike-ai, ralph-orchestrator, **playwright**, codex-bridge | Hold per-target state; sharing → collision. Live in RE project `.mcp.json` (ralph-visible) |
| **→ claude.ai remote** (drop local dupes) | context7, tavily *(exa, wolfram already remote)* | Remote = 0 local RAM; already connected |
| **MERGE** | 4 browser tools → **claude-in-chrome (built-in) + playwright** only; **github ∪ github_cli ∪ bridge → one** | Kill redundancy |
| **DROP entirely** | **mcp-funnel** (superseded by gateway + native Tool Search), **plugin:semgrep** (Pro engine ~1 GB → gateway OSS/CLI), plugin:chrome-devtools-mcp, firefox-devtools, chrome-devtools, plugin:local-mcp-bridge | Pure overhead / redundant |

*Note:* `meta-tool` and its `.mjs` children (deepscan, qlty) are user-authored — candidate to merge into one quality server during Spec 3 / repo reconciliation; for Spec 1 they go to the gateway as-is.

## 5. Cross-AI Registration (one endpoint, one entry per client)

- **Claude:** `~/.claude.json` **user scope** → single `gateway` (http) entry. RE project `.mcp.json` → RE fleet (direct) **+ gateway pointer** (so ralph's `project,local` sources reach it).
- **Codex:** `~/.codex/config.toml` → `[mcp_servers.gateway]` with `url = "http://127.0.0.1:<PORT>/mcp"` (streamable-http). **Per-backend namespacing enabled** in 1mcp to prevent the `web` collision (see §8).
- **Antigravity:** its MCP config → same gateway URL. *(Exact config path/format to verify in P0.)*
- One logical category from the user's view: **gateway + claude.ai**. The RE-project pointer is the *same* gateway URL, not a second category.

## 6. Daemon Lifecycle (Windows)

- Run 1mcp as a background service: Task Scheduler at-logon (or NSSM). Bind **127.0.0.1 only** (no external exposure).
- **Lazy-spawn** backends on first tool call; idle backends not resident.
- **Secrets:** keep as `${ENV_VAR}` references; concrete values in a non-git daemon env file with locked ACLs. No secrets in repo. *(Validate required env present at startup.)*
- `mcp-reaper.ps1` retained as an optional safety-net schedule (far less needed once sharing eliminates per-session multiplication).
- **Health/failure mode:** thin health check + auto-restart; documented degradation — if the daemon is down, sessions lose gateway tools until restart (RE/local tools unaffected).

## 7. Migration Plan (phased, reversible)

- **P0 — Spike:** install 1mcp on Windows; point at ONE test backend; verify a Claude session reaches it over HTTP, and a Codex session too. **Go/no-go.** No-go → fallback `sparfenyuk/mcp-proxy`.
- **P1 — Build gateway config:** port the ~35 stateless servers (commands/args/env) from `~/.mcp.json` + `~/.claude.json`; assign domain tags (research/web/dev/quality/infra/social) mirroring the 6 funnel profiles.
- **P2 — Service:** run 1mcp as a logon service; confirm lazy-spawn + health.
- **P3 — Register:** add gateway entry to Claude (user), Codex (toml), Antigravity; add gateway pointer to RE project `.mcp.json`.
- **P4 — Collapse & dedup:** gut home `~/.mcp.json`; disable redundant plugins (`semgrep`, `chrome-devtools-mcp`); remove `mcp-funnel`; drop browser/`context7`/`tavily` local dupes.
- **P5 — Verify:** tool availability per AI; RAM remeasure (reuse this session's per-server profiler); ralph headless smoke test; Codex namespace clean; rollback rehearsal.
- **Backups:** timestamped copies of `~/.claude.json`, `~/.mcp.json`, `~/.codex/config.toml`, Antigravity config before every edit. One-command restore script.

## 8. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 1mcp Windows support unverified | P0 spike; fallback `sparfenyuk/mcp-proxy` |
| Stateful server shared → collision | RE fleet + playwright kept LOCAL, never in gateway |
| `~/.claude.json` live-rewritten by running sessions → lost update | Re-read/compare-mtime/merge-retry; prefer `claude mcp` CLI; backup first |
| Tool **namespace collisions** across AIs (the `web` error) | 1mcp per-backend tool prefixing; rename offending namespace; verify in P5 |
| Daemon down = no gateway tools | Auto-restart service + health check + documented degradation |
| Parallel session editing same configs | Coordinate; avoid concurrent writes; scoped edits + diff review |
| Secret leakage | `${ENV}` refs only; non-git env file, locked ACLs; startup validation |

## 9. Testing / Verification

- **Before/after RAM** measurement (per-server working-set profiler from this session).
- **Tool-availability smoke test:** one representative tool per gateway backend callable from each AI.
- **ralph headless** smoke test (RE fleet + gateway via project scope).
- **Codex** session free of namespace-collision error.
- **Daemon-down** behavior + auto-restart verified.
- **Rollback** rehearsal from backup.

## 10. Program Roadmap (beyond Spec 1)

- **Spec 2 — `mcp-manager` TUI** (Textual): control planes = Claude · Codex · **gateway** · Antigravity; loadouts = gateway tag presets; status/enable/disable/auth-handoff/bulk. Adapts the user's mcp-manager mission (funnel plane → gateway plane). Depends on Spec 1.
- **Spec 3 — User-authored skill consolidation:** inventory user-made vs marketplace skills (marketplace untouched — auto-updates); dedup/merge; cross-AI distribution.
- **Closing tasks:** (a) **investigate & fix Codex `tools.namespace 'web' collides`** (likely a backend exposing a `web` namespace clashing with Codex's built-in web tool → namespace/prefix it); (b) **reconcile `agent-skills-toolchain` repo** to the established ground truth — refactor, update, document, trim, clear.

## 11. Sources

- CC issue [#28860 — share MCP processes across sessions](https://github.com/anthropics/claude-code/issues/28860)
- mcp-funnel [issue #95 — shared daemon](https://github.com/chris-schra/mcp-funnel/issues/95); [repo](https://github.com/chris-schra/mcp-funnel)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp.md)
- [1mcp](https://github.com/1mcp-app/agent) · [docs](https://docs.1mcp.app/reference/architecture)
- [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) · [shared-daemon walkthrough](https://shyamverma.com/shared-mcp-servers-claude-code)
- [Docker MCP Gateway](https://github.com/docker/mcp-gateway) · [mcpjungle](https://github.com/mcpjungle/MCPJungle)
