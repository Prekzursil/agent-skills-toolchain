---
title: research-1
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/research-1
---

## SOTA: MCP centralization + multi-session concurrency — findings & recommendation

### 0. Recall (basic-memory, two requested notes)
The two notes are not lost — they live under permalinks `reference_mcp_live_toggle_verdict_2026-07-06` and `reference_mcp_nodrift_architecture_2026-07-04` (titles didn't resolve; content recovered from `MEMORY.md` always-on summaries + the two 2026-07-13 harness notes that supersede them):
- **Live-toggle verdict (DEFINITIVE):** Claude Code has **NO robust live/bulk/per-session MCP toggle**. It ignores `tools/list_changed` (upstream #50515/#50339). Only real levers: the `/mcp` **UI (manual, one-at-a-time)** or `--mcp-config` **at launch**. Funnel/plugin re-namespacing all hit the same wall. Real fix depends on an Anthropic `/mcp reload` (#2756). *(Confidence: almost certain, 90-99% — verified empirically in that note.)*
- **No-drift architecture:** canonical `~/.mcp.json` → `promote-mcp-userscope.ps1` → **USER scope** → per-project RAM control via `.mcp-disabled-defaults.json` (7 heavy-Python servers off by default). Rule: new server → **canon only + re-promote**; **never hand-edit** a per-tree `.mcp.json`. Promotion is **Claude-CLOSED-only** (a live session clobbers `~/.claude.json` on exit).
- **Superseded by (2026-07-13, current truth):** decision **D2 = repo-as-source-of-truth**: the versioned `agent-skills-toolchain` repo is now SSOT, mirrored at `tools/mcp/canonical-mcp-servers.json`, deploy **repo→live**, `~/.mcp.json` self-declares canonical. The `promote-mcp-userscope.ps1 -PruneExtraUserServers` step is **blocked-on-restart** (needs Claude fully closed).

### 1. Claude Code scope model + precedence (SOTA, verified)
Three scopes, **narrower wins**: **Local > Project > User > Plugins > claude.ai connectors**.
- **Local** — this machine + this project, stored in `~/.claude.json` (per-project key). Personal override.
- **Project** — `.mcp.json` at repo root, team-shared/committed.
- **User** — global block in `~/.claude.json`, available in every project.
Storage: user + local live in `~/.claude.json`; project lives in the repo's `.mcp.json`. *(Confidence: almost certain — [Claude Code settings docs](https://code.claude.com/docs/en/settings), [ClaudeWorld scope guide](https://claude-world.com/articles/mcp-scope-inheritance/).)*

### 2. Known live-reload / toggle limitations (the constraint that kills naive sync)
MCP servers are read **only at session startup**. Editing `~/.claude.json`/`.mcp.json` or `claude mcp add` mid-session writes the file but the running process does **not** pick it up — you must exit and relaunch, losing in-memory context. No `/mcp reload`, no `claude mcp reload`, no hot-reload built in; multiple open feature requests: [#17675](https://github.com/anthropics/claude-code/issues/17675), [#36643](https://github.com/anthropics/claude-code/issues/36643), [#46426](https://github.com/anthropics/claude-code/issues/46426), [#54136](https://github.com/anthropics/claude-code/issues/54136). Community workaround only: third-party `mcp-hot-reload` / custom `/reload` shell-signal commands. *(Confidence: almost certain, 90-99%.)*
**Implication:** a live session writing `~/.claude.json` on exit is exactly why the "promote" file-sync is fragile (clobber-on-close) — the config layer is **not** safe to mutate while sessions are live.

### 3. Multi-session concurrency — the duplicate-process problem (this is the crux)
Claude Code spawns **one MCP process set per session** (stdio transport = one child per client). With N sessions × M servers you get up to **N×M processes**, no memory cap:
- 4 sessions × 6 servers → ~42 processes / ~1.9 GB ([#28860](https://github.com/anthropics/claude-code/issues/28860), **closed as duplicate — not implemented**); 15 sessions × 34 servers → **kernel panic** ([#45880](https://github.com/anthropics/claude-code/issues/45880)); 7 sessions → 172 procs / ~3 GB ([shyamverma](https://shyamverma.com/shared-mcp-servers-claude-code)).
- Orphan leaks on session/subagent exit ([#40667](https://github.com/anthropics/claude-code/issues/40667), [#33947](https://github.com/anthropics/claude-code/issues/33947)); Windows double-spawn (directMcpHost + LocalMcpServerManager) [#53134](https://github.com/anthropics/claude-code/issues/53134).
- **Singleton-resource conflict** ([#40220](https://github.com/anthropics/claude-code/issues/40220)): stdio servers holding a singleton (e.g. Telegram `getUpdates`, a bound port, a DB lock) **fight across sessions** — session 2's process kills session 1's connection. This directly matches your prior `mcp_doctor reap` incident (machine-wide reap killed sibling sessions' live MCP children).
*(This corroborates the workspace's own `MEMORY.md` RAM-OOM / per-session-dup diagnosis — #28860 is the canonical upstream ticket.)*

### 4. SSOT + concurrency SOTA: the gateway/aggregator pattern (the robust answer)
The 2026 ecinsystem answer to server sprawl is **not file-sync** — it is an **MCP gateway / aggregator**: one long-lived process federates many backend servers behind a **single HTTP/SSE (Streamable-HTTP) endpoint**, presenting a unified, namespaced tool catalog ([Hey It Works Q1-2026 survey of 17 gateways](https://www.heyitworks.tech/blog/mcp-aggregation-gateway-proxy-tools-q1-2026), [AgentGateway multiplexing](https://agentgateway.dev/blog/2026-02-20-mcp-multiplexing-tool-access-agentgateway/), [MetaMCP three-level hierarchy](https://chatforest.com/guides/mcp-gateway-proxy-patterns/)). Properties that solve every sub-question in the task:
- **Duplicate-process avoidance:** N sessions all connect to ONE gateway endpoint → one backend process set, not N×M. Kills #28860/#45880.
- **Concurrent requests to the same MCP:** HTTP/Streamable-HTTP transport is **built to multiplex concurrent clients**; stdio is not. The gateway owns the singleton, sessions are just HTTP clients → resolves #40220. Latency cost ~10-50ms (auth+route+log).
- **Config-as-SSOT:** the **gateway's own config** becomes the true single source of server inventory. Claude Code sees only a tiny `type: http, url: …` stub per gateway → also shrinks the tool-catalog baseline (your window-bloat problem: 63 user-scope servers ≈ 421k tok / 52% of window).
- **Live inventory changes** happen in the gateway (restart the gateway, not every Claude session) — sidesteps the no-hot-reload wall for the servers *behind* it.
*(Confidence: likely-to-very-likely, 65-85%, that a gateway is the right primary architecture; the pattern is proven but no single tool satisfies all 8 enterprise criteria yet per the Q1-2026 survey — pick a lean one.)*
**You already run this pattern:** `agent-mail` (always-on 8812, `/api/health`), `cloud-hub`, and `search-hub` are HTTP aggregators. The recommendation generalizes what's already working.

### 5. Current on-disk divergence (measured this session)
- Canonical live: `~/.mcp.json` (8851 B, 2026-07-13 04:06). Per-project mask: `~/.claude/.mcp-disabled-defaults.json` (3014 B). Promote script: `~/.claude/hooks/mcp-userscope-sync/promote-mcp-userscope.ps1`.
- **D: divergence (the risk):** `D:\Research\.mcp.json` (8538 B — a **stale config copy**, not a backup), plus **two stale clones of the promote script** at `D:\gem-wave-b\hooks\…` and `D:\pr-b-clone\hooks\…`, plus dated `D:\Backups\config\*\.mcp.json` (legit backups). The daily backups are fine; the **`D:\Research\.mcp.json` + the two D: promote-script clones are drift sources** — parallel copies that can be hand-edited and diverge.
- Repo mirror: `agent-skills-toolchain/tools/mcp/canonical-mcp-servers.json` (per the committed D2 reconcile, branch `chore/enshrine-runtime-config` @ `5d2fca2`, local-only).

### 6. RECOMMENDATION — unify robustly, NOT via the failed sync
The failed approach = **bidirectional file-sync** (promote-script copying between `~/.mcp.json`, user scope, and D: copies), which is brittle because (a) live sessions clobber `~/.claude.json` on close, (b) N copies with no single owner drift, (c) it does nothing about the N×M process explosion. Replace it with a **two-layer generate-don't-sync design**:

**Layer A — Governance SSOT (one-directional generate):**
1. Make `agent-skills-toolchain/tools/mcp/canonical-mcp-servers.json` the **sole editable source** (matches committed D2). Every server add/edit happens ONLY here.
2. Replace the copy-sync promote step with an **idempotent generator**: `canonical → render → ~/.mcp.json` + user-scope block. Generation is **one-way and reproducible** (a build step), never a two-way merge. Run it only with **Claude fully closed** (the clobber constraint is unavoidable at the `~/.claude.json` layer) — or better, write the generated output to a project/user `.mcp.json` that Claude reads at launch, avoiding the `~/.claude.json` write race entirely.
3. **Retire D: as a config source:** `D:\Research\.mcp.json` and the two `D:\*\hooks\…\promote-mcp-userscope.ps1` clones should be **deleted or regenerated read-only** from canonical. Keep `D:\Backups\config\*` as timestamped backups only (never read as live config). Add a drift-check (hash canonical vs live vs any D: copy) to the existing edit-guard gate.
4. Add the **canonical-config edit-guard** (already planned as Task 8, shadow-first): block/flag any hand-edit to a rendered `~/.mcp.json` or a stray D: copy, directing edits back to canonical.

**Layer B — Runtime consolidation (kills duplication + concurrency conflicts):**
5. Keep the **lean-catalog** posture that's already working: `ENABLE_TOOL_SEARCH=auto:5` deferral ON, `.mcp-disabled-defaults.json` masking the 7 heavy-Python servers per-project. This is the per-session-profile lever the upstream issues ask for.
6. **Migrate the heavy/always-on stdio servers behind local HTTP gateways** (extend the agent-mail/cloud-hub/search-hub pattern). Then Claude Code's canonical config references a **single `type: http` stub per gateway** instead of N stdio server defs. Result: multiple sessions share ONE backend process set (fixes #28860), concurrent requests multiplex natively (fixes #40220), and the tool-catalog baseline shrinks dramatically. Guard each gateway with an always-on supervisor + `/health` poll (the `MCPAgentMailSupervisor` model).
7. Leave genuinely lightweight, personal, low-RAM servers as **user-scope stdio** (cheap, no gateway overhead); reserve **project-scope `.mcp.json`** strictly for repo-specific tools; never use local scope as a hidden drift channel.

**Net:** SSOT = the versioned canonical JSON (generate, don't sync); duplication + concurrency = solved at runtime by HTTP-gateway consolidation, not by copying files. This removes the clobber-race, the D: divergence, and the N×M process explosion in one coherent design, and aligns with both the 2026 gateway SOTA and the workspace's own already-proven aggregator infrastructure.

*Overall confidence: the scope model, live-reload gap, and process-duplication facts are almost-certain (upstream-issue + docs verified, 90-99%). The gateway-as-primary-fix is likely-to-very-likely (65-85%) — proven pattern, but requires per-server migration effort and no gateway is turnkey-complete per the Q1-2026 survey.*

### Sources
- [Claude Code settings docs](https://code.claude.com/docs/en/settings) · [ClaudeWorld MCP scope/precedence](https://claude-world.com/articles/mcp-scope-inheritance/)
- Live-reload gap: [#17675](https://github.com/anthropics/claude-code/issues/17675), [#36643](https://github.com/anthropics/claude-code/issues/36643), [#46426](https://github.com/anthropics/claude-code/issues/46426), [#54136](https://github.com/anthropics/claude-code/issues/54136)
- Process duplication/concurrency: [#28860](https://github.com/anthropics/claude-code/issues/28860) (closed-dup), [#45880](https://github.com/anthropics/claude-code/issues/45880), [#40667](https://github.com/anthropics/claude-code/issues/40667), [#40220](https://github.com/anthropics/claude-code/issues/40220), [#53134](https://github.com/anthropics/claude-code/issues/53134), [shyamverma: shared MCP servers](https://shyamverma.com/shared-mcp-servers-claude-code)
- Gateway/aggregator SOTA: [Hey It Works — Q1-2026 gateway survey](https://www.heyitworks.tech/blog/mcp-aggregation-gateway-proxy-tools-q1-2026), [AgentGateway multiplexing](https://agentgateway.dev/blog/2026-02-20-mcp-multiplexing-tool-access-agentgateway/), [ChatForest gateway/proxy patterns (MetaMCP)](https://chatforest.com/guides/mcp-gateway-proxy-patterns/)
- basic-memory: `main/harness/config-drift-audit-auto-compact-fix-2026-07-13`, `main/harness/reconcile-committed-2026-07-13-enshrine-runtime-config`; MEMORY.md summaries of `reference_mcp_live_toggle_verdict_2026-07-06` + `reference_mcp_nodrift_architecture_2026-07-04`