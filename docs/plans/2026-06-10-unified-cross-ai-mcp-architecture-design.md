# Unified, Cross-AI MCP Architecture — Design Spec (v2)

**Date:** 2026-06-10 · **Status:** v2, post Design-Review-Gate round 1 (addresses all blockers) · pending re-gate → Plan Review → implementation
**Scope:** Spec 1 of a 3-spec program (see §12 Roadmap)
**Revision note:** v2 rewrites §3, §4, §6, §7 and adds §5 (Security model) after a 5-agent review flagged: lazy-spawn-as-RAM unproven, no gateway auth, wrong stateful/stateless split, no atomic cutover, tool-rename side-effect, unresolved port/tags/Antigravity.

---

## 1. Problem & Motivation

Diagnosed this session (process forensics + source reading + official docs + precedent):

- **Per-session fleet duplication.** Claude Code spawns its *own* copy of every stdio MCP server per session ([CC #28860](https://github.com/anthropics/claude-code/issues/28860)). ~52 servers load from the home dir; two sessions ≈ **8.4 GB** MCP working set; semgrep Pro engine ≈ **920 MB resident per session** (plugin layer, since semgrep 1.165 on 2026-06-05).
- **`mcp-funnel` does not save RAM.** Source-confirmed eager-spawn of all backends; `enableDynamicDiscovery` hides *schemas* only ([#95](https://github.com/chris-schra/mcp-funnel/issues/95)). Stdio-only as a server → can't be a shared HTTP daemon.
- **Native Tool Search** (CC v2.1.121+) already defers tool schemas → funnel's token role is redundant.
- **Five config categories** with duplicates; user wants **one local category + claude.ai remotes**, **cross-AI** (Claude/Codex/Antigravity).

**Precedent:** a shared HTTP MCP daemon cut **172→33 processes, ~3 GB→<1 GB** across 7 sessions ([shyamverma.com](https://shyamverma.com/shared-mcp-servers-claude-code)). Official docs: **stdio = per-session child process (not lazy); HTTP/SSE = a connection, not duplicated per session.**

## 2. Goal & Success Criteria

One shared, low-overhead MCP backend fleet reachable by all local AIs, collapsing 5 categories into **one logical layer + claude.ai remotes**.

- **G1** A fresh Claude/Codex/Antigravity session sees its intended tools (verified against the per-AI inventory in §11, not "all").
- **G2** Steady-state MCP RAM materially drops (target <1.5 GB typical-session; **contingent on P0 proving lazy = process-spawn deferral** — see §3a). If P0 disproves lazy-spawn, G2 is renegotiated per §3a fallbacks.
- **G3** ralph headless (`--setting-sources project,local`) keeps working — guaranteed because all ralph-needed tools (RE fleet) stay **LOCAL/stdio**, independent of the daemon (§4, §6).
- **G4** No destruction of enable/disable curation; **end-to-end reversible** (configs + plugin state + funnel + service), one-command restore rehearsed in P0 (§7).
- **G5** Codex `tools.namespace 'web' collides` resolved (§5, §8).
- **G6** Gateway is authenticated and least-privilege-scoped per loadout (§5).

## 3. Architecture

```
                 ┌──────────────────────────────────────┐
 Claude Code ───▶│  1mcp gateway daemon                  │ backends, started
 Codex CLI   ───▶│  http://127.0.0.1:7820/mcp            │ on demand & SHARED:
 Antigravity ───▶│  • bearer-token auth + Origin check   │──▶ MCP backend procs
 (any client)───▶│  • per-connection ?tags= loadouts     │   (one set, all AIs)
                 │  • per-backend namespacing (selective) │
                 └──────────────────────────────────────┘
   untouched:  claude.ai remote connectors (0 local RAM)
   LOCAL only (stateful / RE / ralph-critical):  ida·ghidra·binary-ninja·frida·
               cheatengine·hexstrike·playwright·codex-bridge·basic-memory·postgres·docker
```

**Gateway tech:** `1mcp` (`@1mcp/agent` v0.32.2). Confirmed by review: per-connection tag filtering (`?tags=`) and per-backend namespacing exist. **Unconfirmed and therefore P0-gated:** whether "lazy loading" defers the backend *process spawn* (RAM) or only the *tool schema* (tokens), and whether 0.32.2 supports a bearer-token transport. **Fixed loopback port: 7820** (verify free in P0; `--port`).

### 3a. P0 — Hard Go/No-Go Gates (gate everything else)

P0 is a throwaway spike with **explicit, measured** pass conditions. Proceed only if **all** pass:

- **Gate A — Lazy = PROCESS deferral (RAM).** Configure 5 backends, call **0** tools, assert their child PIDs are **absent** (per-server profiler from this session). Then call 1 tool → assert **only that backend** spawns. *If A fails: 1mcp lazy is schema-only → G2 unreachable by 1mcp AND by the mcp-proxy fallback (also eager). Decision point → pivot to **Docker MCP Gateway** (real on-demand container lifecycle) OR accept a token-only/`reaper`-assisted outcome. Do not proceed to P1 on the RAM premise without A.*
- **Gate B — Cross-session sharing.** 2nd concurrent session adds **0** new backend procs for an already-warm backend.
- **Gate C — Per-connection tag scoping.** Claude `?tags=research` and Codex `?tags=dev` simultaneously see **disjoint** tool sets.
- **Gate D — Auth + namespacing.** Bearer-token transport works (unauthenticated request rejected); selective namespacing renames **only** the colliding backend, not all.
- **Gate E — Antigravity.** Antigravity actually connects to a streamable-http MCP endpoint. *If E fails (stdio-only): pre-committed fallback = ship cross-AI for Claude+Codex, defer Antigravity to a follow-up; G1 scope narrows accordingly — acceptable.*
- **Gate F — Idle eviction.** Determine 1mcp's idle-timeout/eviction policy; if backends never evict, steady-state RAM converges to eager → document the true ceiling.

Rollback scaffolding (§7) is built and rehearsed **before** P0's first edit.

## 4. Server Disposition Map — with concurrency classification

Reviewers correctly rejected a blanket "stateless → safe." Each server is classed: **(S) idempotent-stateless** (safe to share), **(I) auth-scoped single identity** (shareable but one credential blast-radius), **(M) stateful-mutable** (NOT safely shared → LOCAL or documented serialization).

| Disposition | Servers (class) | Rationale |
|---|---|---|
| **→ Gateway** | tooluniverse(S), scholarly-access(S), academia(S), rdkit(S), schrodinger(S), huggingface(S), firecrawl(S), scrapegraph(S), apify(S), markitdown(S), pdf-reader(S), excel(S), ocr(S), repomix(S), mcp-graphql(S), **github(I)**, linear(I), notion(I), figma(I), codacy(I), codecov(I), deepsource(I), deepscan(I), qlty(I), sonarqube(I), sentry(I), semgrep-OSS(S), digitalocean(I), browserstack(I), tiktok(I), insta-mcp(I), fb-messenger(I) | Stateless or single-identity request/response; safe behind shared daemon. (I)-class share ONE token → §5 least-privilege + default-deny scoping. |
| **LOCAL (moved from gateway in v2)** | **basic-memory(M)** — shared markdown+vector vault, concurrent writes corrupt; **postgres(M)** — connection/txn state; **docker(M)** — container name/port collisions | Concurrent multi-session access through one shared child = corruption/races. Keep local/stdio (or per-client) until a serialization guarantee is proven. |
| **LOCAL (stateful / RE / ralph)** | ida-pro-mcp, ghidra-mcp, binary-ninja-mcp, frida-mcp, cheatengine, hexstrike-ai, ralph-orchestrator, **playwright**, codex-bridge | Per-target state; sharing → collision. RE fleet in RE-project `.mcp.json` (ralph-visible, daemon-independent → G3). |
| **→ claude.ai remote** (drop local dupes) | context7, tavily *(exa, wolfram already remote)* | 0 local RAM; already connected. |
| **MERGE** | 4 browser tools → **claude-in-chrome + playwright** only; **github ∪ github_cli ∪ bridge → one** | Kill redundancy. |
| **DROP** | **mcp-funnel** (superseded), **plugin:semgrep** (Pro ~1 GB), plugin:chrome-devtools-mcp, firefox-devtools, chrome-devtools, plugin:local-mcp-bridge | Redundant / replaced. |

*Open in v2:* whether 1mcp multiplexes ONE backend child across connections or one-per-connection (affects both the (M) concurrency risk and the sharing/RAM claim) — answered in P0 Gate A/B. If one-per-connection, (M) servers may be gateway-safe after all; re-classify post-P0.

## 5. Security Model (new in v2)

**Trust boundary = the loopback port. Adversaries in scope:** other local processes (same/any user — Windows ports have no ACL), prompt-injected AI sessions (firecrawl/scrapegraph/apify/tavily feed web content into the same gateway), and malicious supply-chain code. **NOT** just remote attackers.

**Mandatory controls (design requirements, not deferred):**
1. **Bearer-token auth** on every gateway request (1mcp serve boundary); token in the ACL-locked env file; distributed to the 3 clients via their config headers/env. Loopback bind is necessary **and not sufficient**.
2. **Origin/Host allowlist** (localhost only) → DNS-rebinding/forged-fetch defense.
3. **Per-loadout default-deny scoping** for destructive (I)-backends: `github`(write), `digitalocean`, `docker`, `postgres` require an explicit opt-in loadout; research/web loadouts cannot reach them. Scoping is a **security** requirement (confused-deputy mitigation), realized via tag presets.
4. **RE/exploitation fleet NEVER on the gateway** — hard invariant; P5 asserts no RE backend appears in the gateway tool list. Spec 2's "gateway plane" must not migrate these onto the shared surface.
5. **Env-file + backup ACLs:** `icacls` owner+SYSTEM only; backups outside any git tree, restrictive ACL, retention/shred policy; **encrypt credential-bearing backups** (user already uses `.enc` for claude-swap). Backups include `~/.mcp-funnel-master.json` (the current source of truth) and `~/.codex/config.toml`.
6. **Supply-chain pinning:** exact versions for every backend (`pkg@x.y.z` / `pkg==x.y.z` / docker `@sha256:`), a version manifest, deliberate update procedure. No `@latest`.
7. **Secret hygiene:** no Authorization/env echo in logs; scrub backend spawn/stderr; `/health` returns no config/token; startup self-check **fails closed** on missing token without printing it.
8. **Run as the logon user, not elevated/SYSTEM.** No future LAN exposure without redesign (TLS + OAuth/PKCE).
9. **Breach runbook:** pre-listed token-rotation steps for the aggregation risk.

## 6. Daemon Lifecycle (Windows)

- **Service manager: NSSM** (auto-restart + ordering/readiness), Task Scheduler at-logon only as a lighter fallback. Bind `127.0.0.1:7820`, run as the user.
- **Readiness:** clients use a retry/health-gated connect; first tool call must not hit a not-ready daemon.
- **Lazy-spawn** per P0 Gate A; idle-eviction per Gate F (documented).
- **Day-2 interim ops (Spec-1 deliverable, before the Spec-2 TUI):** documented commands/PowerShell wrappers to (a) check daemon up + port, (b) list backends and state (idle/spawned/failed), (c) restart, (d) tail logs. Built on 1mcp's own CLI if it exposes these; else thin wrappers.
- **Per-backend spawn-failure UX:** a single backend failing at first-use errors **only that tool**, leaving the rest of the session's gateway tools intact; cause logged. Distinct from daemon-down (whole gateway unavailable; RE/local tools unaffected).

## 7. Migration Plan (phased, reversible, with overlap window)

- **P-1 — Rollback scaffolding FIRST.** One-command `restore` that reverts: all config files (`~/.claude.json`, `~/.mcp.json`, `~/.codex/config.toml`, Antigravity, `~/.mcp-funnel*.json`), **plugin enable-state** (re-enable semgrep/chrome-devtools-mcp), **funnel presence**, and **NSSM service** (stop/remove). Timestamped backups; rehearse the FULL revert once while empty.
- **P0 — Spike & gates** (§3a). Go/no-go.
- **P1 — Build gateway config + tag table** (§11): port ~32 gateway servers with **exact-pinned** versions + per-server tags; gateway starts with 0 backends resident.
- **P2 — Service** (NSSM), health + lazy verified.
- **P3 — Register (additive, non-destructive):** add gateway entry to Claude (user), Codex (toml, namespaced), Antigravity; add gateway pointer to RE-project `.mcp.json`. **Old funnel left intact.**
- **P4 — OVERLAP WINDOW:** gateway AND old funnel both live; verify per-AI tool availability, RAM, ralph smoke, namespace-clean, security smoke (§9) **while the old path still works**. Precondition: no concurrent session writing the target config (quiesce or use `claude mcp` CLI exclusively; coordinate with any parallel session).
- **P5 — Cutover (destructive, only after P4 green):** gut home `~/.mcp.json`, disable redundant plugins, remove funnel, drop browser/context7/tavily dupes. Each step has an **exit criterion + abort trigger**; any red → `restore`.
- **P6 — Final verify + curation diff:** assert no previously-disabled server silently became enabled (diff disabled/enabled sets pre/post); re-run §9 suite.
- **Live-rewrite hazard:** `~/.claude.json` is rewritten by running sessions → re-read/compare-mtime/merge-retry, prefer `claude mcp` CLI; exercised in P4 with a real second session running.

## 8. The Codex `web` namespace collision

Likely a backend exposing a `web` tool namespace clashing with Codex's built-in web tool. Fix via 1mcp **selective** per-backend namespacing (rename only the offender) — confirmed available, verified in P0 Gate D. **If uniform namespacing is the only option,** P5 adds a rename-migration: inventory every name-dependent reference (skills, `settings.json` allowedTools, ralph project config, hooks) and update them. Identify which backend currently exposes `web` during P0.

## 9. Testing / Verification (scripted, pass/fail thresholds)

- **RAM:** per-server profiler; assert typical-session steady-state **< 1.5 GB**; also record worst-case "all-warm" ceiling + idle-eviction behavior.
- **Tool availability:** scripted per-AI, per-backend probe (one representative tool asserted callable) against the §11 inventory.
- **ralph:** headless smoke (RE fleet reachable with daemon stopped → proves G3 independence).
- **Namespace:** assert Codex startup logs do **not** contain the `web collides` string.
- **Security smoke:** (1) unauthenticated request rejected; (2) forged-Origin rejected; (3) gateway tool list contains **no** RE/exploitation backend; (4) a `research` loadout **cannot** invoke github-write/digitalocean/docker/postgres; (5) grep logs + `/health` for token material after a forced backend-auth failure → none.
- **First-call latency:** cold-backend first tool call completes within an agreed threshold (the lazy-spawn tradeoff, verified not assumed).
- **Curation preservation:** pre/post diff of disabled/enabled sets = no silent flips.
- **Rollback:** `restore` returns the machine to pre-migration state end-to-end (rehearsed P-1, re-tested P6).

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Lazy = schema-only (RAM win fails)** | P0 Gate A measures it; fallback = Docker MCP Gateway or renegotiate G2 (mcp-proxy does NOT fix this — it's eager too) |
| Unauthenticated local confused-deputy | Bearer token + Origin check + per-loadout default-deny (§5) |
| Stateful server shared → corruption | basic-memory/postgres/docker moved LOCAL in v2; re-evaluate after P0 multiplexing answer |
| Tool-rename breaks skills/allowlists | Selective namespacing; else P5 rename-migration inventory |
| Destructive cutover strands sessions | P4 overlap window (both paths live) before P5; per-phase abort + `restore` |
| `~/.claude.json` live-rewrite lost-update | mtime-merge-retry + `claude mcp` CLI; tested with a live 2nd session |
| Secret aggregation blast radius | least-privilege tokens, ACL/encrypted env+backups, pinning, breach runbook |
| Antigravity stdio-only | P0 Gate E; pre-committed Claude+Codex fallback |
| ralph daemon dependency | RE fleet stays LOCAL → ralph daemon-independent (G3) |
| Parallel session editing configs | quiesce/coordinate; CLI-only edits during cutover |

## 11. Per-server Tag Table (loadouts) — to finalize in P1

Reconciles the existing 6 funnel profiles (`default|minimal|re|web|quality|data`) with the loadout tags. **`re` is LOCAL, not a gateway loadout.** Destructive-tagged backends are default-deny (§5).

| Tag (loadout) | Gateway backends |
|---|---|
| `research` | tooluniverse, scholarly-access, academia, rdkit, schrodinger, huggingface |
| `web` | firecrawl, scrapegraph, apify, tavily*(remote)*, browserstack |
| `docs` | markitdown, pdf-reader, excel, ocr, repomix |
| `dev` | github, linear, notion, figma, mcp-graphql |
| `quality` | codacy, codecov, deepsource, deepscan, qlty, sonarqube, sentry, semgrep-OSS |
| `infra` *(default-deny)* | digitalocean *(docker/postgres are LOCAL in v2)* |
| `social` | tiktok, insta-mcp, fb-messenger |

*(Exact mapping + which tags each AI/loadout requests is a P1 artifact; `minimal`/`default` map to tag combinations.)*

## 12. Program Roadmap (beyond Spec 1)

- **Spec 2 — `mcp-manager` TUI** (Textual): planes = Claude · Codex · **gateway** · Antigravity; loadouts = the §11 tag presets (shared deliverable from Spec 1, not re-derived). Adapts the user's mcp-manager mission (funnel plane → gateway plane). Depends on Spec 1.
- **Spec 3 — User-authored skill consolidation:** inventory user-made vs marketplace skills (marketplace untouched); dedup/merge; cross-AI distribution.
- **Closing tasks:** (a) **fix Codex `web` collision** (covered by §8); (b) **reconcile `agent-skills-toolchain` repo** to the captured final ground truth (gate on Spec 1 completion so reconciliation isn't against a moving target).

## 13. Sources

- [CC #28860](https://github.com/anthropics/claude-code/issues/28860) · mcp-funnel [#95](https://github.com/chris-schra/mcp-funnel/issues/95) / [repo](https://github.com/chris-schra/mcp-funnel)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp.md) · [1mcp](https://github.com/1mcp-app/agent) / [docs](https://docs.1mcp.app/reference/architecture)
- [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) · [shared-daemon walkthrough](https://shyamverma.com/shared-mcp-servers-claude-code) · [Docker MCP Gateway](https://github.com/docker/mcp-gateway)
