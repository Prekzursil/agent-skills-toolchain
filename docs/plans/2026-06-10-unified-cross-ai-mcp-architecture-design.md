---
title: 2026-06-10-unified-cross-ai-mcp-architecture-design
type: note
permalink: dqverify-repo-20261013/docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design
---

# Unified, Cross-AI MCP Architecture — Design Spec (v2.1)

**Date:** 2026-06-10 · **Status:** v2.1, **Design-Review-Gate PASSED** (5/5 approve, round 2) — v2.1 folds in round-2 non-blocking refinements · pending user review → Plan Review Gate → implementation
**Scope:** Spec 1 of a 3-spec program (see §12 Roadmap)
**Revision note:** v2 rewrote §3-§7 + added §5 (Security) after round 1 flagged: lazy-spawn-as-RAM unproven, no gateway auth, wrong stateful/stateless split, no atomic cutover, tool-rename side-effect, unresolved port/tags/Antigravity. **v2.1** adds: split Gate D into D1-auth/D2-namespace with explicit fallbacks; Gate A as master-gate-first; pinned RAM/latency acceptance numbers; NSSM-as-interactive-user; client-config token ACL; per-step P5 abort criteria; frozen §11 tag-table contract; connection-bound loadout semantics; default-loadout-not-"all" guard.

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
- **G2** Steady-state MCP RAM materially drops — **two pinned acceptance numbers**: (a) *typical session* < **1.5 GB**; (b) *all-warm ceiling* (every gateway backend spawned at once) < **3 GB** (vs. ~8 GB today). **Contingent on P0 proving lazy = process-spawn deferral AND a working idle-eviction** (Gate A + Gate F) — see §3a. If P0 disproves either, G2 is renegotiated per §3a fallbacks. First-call latency to a cold backend < **5 s** (the lazy-spawn UX tradeoff; if exceeded, surface a "warming…" state per §6).
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

P0 is a throwaway spike with **explicit, measured** pass conditions. **Gate A runs FIRST and is the master gate** — it determines whether the entire RAM premise (and therefore the §7 plan + §11 tag design) is valid; do not build P1 until A passes. Proceed only if **all** pass:

- **Gate A (MASTER, run first) — Lazy = PROCESS deferral (RAM).** Configure 5 backends, call **0** tools, assert their child PIDs are **absent** (per-server profiler from this session). Then call 1 tool → assert **only that backend** spawns. *If A fails: 1mcp lazy is schema-only → G2 unreachable by 1mcp AND by the mcp-proxy fallback (also eager). Decision point → pivot to **Docker MCP Gateway** (real on-demand container lifecycle). **A Docker pivot invalidates §7 (P1-P6) and §11 (1mcp `?tags=`/namespacing semantics) → triggers a full re-plan, not a config swap** (see §10).*
- **Gate B — Cross-session sharing + multiplexing model.** 2nd concurrent session adds **0** new backend procs for an already-warm backend. **Also record:** does 1mcp run ONE backend child multiplexed across connections, or one-per-connection? (This answer drives the §4 (M)-class re-classification decision record.)
- **Gate C — Per-connection tag scoping.** Claude `?tags=research` and Codex `?tags=dev` simultaneously see **disjoint** tool sets.
- **Gate D1 — Transport auth.** A bearer-token (or equivalent) transport works in 1mcp 0.32.2; an unauthenticated request to `:7820` is **rejected**. *If D1 fails (0.32.2 has no transport auth): pre-committed fallback = (a) pin/upgrade to a 1mcp version that supports it, else (b) front 1mcp with a thin authenticating loopback reverse-proxy (e.g. a tiny local token-checking proxy), else (c) **No-Go**. Do NOT ship a no-auth loopback gateway as a silent fallback — §5.1 auth is mandatory.*
- **Gate D2 — Selective namespacing.** Namespacing renames **only** the colliding backend (the `web` offender), not all tools. *If only uniform namespacing exists → trigger the §8 rename-migration inventory.*
- **Gate E — Antigravity.** Antigravity actually connects to a streamable-http MCP endpoint (config path/format confirmed). *If E fails (stdio-only): pre-committed fallback = ship cross-AI for Claude+Codex, defer Antigravity; G1 scope narrows accordingly — acceptable.*
- **Gate F — Idle eviction.** Determine 1mcp's idle-timeout/eviction policy. *If backends never evict → steady-state converges to eager; treat **A-pass + F-fail** as routing to the same Docker-Gateway pivot as A-fail unless the measured all-warm ceiling (G2) is still < 3 GB.*

Rollback scaffolding (§7 P-1) is built and rehearsed **before** P0's first edit.

## 4. Server Disposition Map — with concurrency classification

Reviewers correctly rejected a blanket "stateless → safe." Each server is classed: **(S) idempotent-stateless** (safe to share), **(I) auth-scoped single identity** (shareable but one credential blast-radius), **(M) stateful-mutable** (NOT safely shared → LOCAL or documented serialization).

| Disposition | Servers (class) | Rationale |
|---|---|---|
| **→ Gateway** | tooluniverse(S), scholarly-access(S), academia(S), rdkit(S), schrodinger(S), huggingface(S), firecrawl(S), scrapegraph(S), apify(S), markitdown(S), pdf-reader(S), excel(S), ocr(S), repomix(S), mcp-graphql(S), **github(I)**, linear(I), notion(I), figma(I), codacy(I), codecov(I), deepsource(I), qlty(I), sonarqube(I), sentry(I), semgrep-OSS(S), digitalocean(I), browserstack(I), tiktok(I), insta-mcp(I), fb-messenger(I) | Stateless or single-identity request/response; safe behind shared daemon. (I)-class share ONE token → §5 least-privilege + default-deny scoping. |
| **LOCAL (moved from gateway in v2)** | **basic-memory(M)** — shared markdown+vector vault, concurrent writes corrupt; **postgres(M)** — connection/txn state; **docker(M)** — container name/port collisions | Concurrent multi-session access through one shared child = corruption/races. Keep local/stdio (or per-client) until a serialization guarantee is proven. |
| **LOCAL (stateful / RE / ralph)** | ida-pro-mcp, ghidra-mcp, binary-ninja-mcp, frida-mcp, cheatengine, hexstrike-ai, ralph-orchestrator, **playwright**, codex-bridge | Per-target state; sharing → collision. RE fleet in RE-project `.mcp.json` (ralph-visible, daemon-independent → G3). |
| **→ claude.ai remote** (drop local dupes) | context7, tavily *(exa, wolfram already remote)* | 0 local RAM; already connected. |
| **MERGE** | 4 browser tools → **claude-in-chrome + playwright** only; **github ∪ github_cli ∪ bridge → one** | Kill redundancy. |
| **DROP** | **mcp-funnel** (superseded), **plugin:semgrep** (Pro ~1 GB), plugin:chrome-devtools-mcp, firefox-devtools, chrome-devtools, plugin:local-mcp-bridge | Redundant / replaced. |

*Open (P0 decision record):* whether 1mcp multiplexes ONE backend child across connections or one-per-connection (Gate B) has **opposite** implications — *one-shared-child* preserves the RAM win but keeps (M)-servers corruption-prone (→ stay LOCAL); *per-connection* makes (M)-servers gateway-safe but weakens the sharing/RAM win. **P1 must record the measured answer as an explicit decision** justifying each (M) placement; the same review re-runs the §5 scoping analysis (corruption AND token-blast-radius), not just the concurrency check. **github(I)** specifically: pending the multiplexing answer, treat concurrent web-loadout vs dev-loadout access to one warm github backend as a §5.3 default-deny concern — if one-shared-child, consider github write-ops LOCAL/opt-in only.

## 5. Security Model (new in v2)

**Trust boundary = the loopback port. Adversaries in scope:** other local processes (same/any user — Windows ports have no ACL), prompt-injected AI sessions (firecrawl/scrapegraph/apify/tavily feed web content into the same gateway), and malicious supply-chain code. **NOT** just remote attackers.

**Mandatory controls (design requirements, not deferred):**
1. **Bearer-token auth** on every gateway request (1mcp serve boundary; verified by P0 Gate D1, with the reverse-proxy/version-pin/No-Go fallback there); token in the ACL-locked env file; distributed to the 3 clients via their config headers/env. **Distributing the token into `~/.claude.json` / `~/.codex/config.toml` / Antigravity config makes those files token-bearing → they inherit the §5.5 ACL + backup-encryption requirement.** Loopback bind is necessary **and not sufficient**.
2. **Origin/Host allowlist** (localhost only) → DNS-rebinding/forged-fetch defense.
3. **Per-loadout default-deny scoping** for destructive (I)-backends: `github`(write), `digitalocean`, `docker`, `postgres` require an explicit opt-in loadout; research/web loadouts cannot reach them. **Enforced at config-generation time** — the tag table (§11) must guarantee a `web`/`research` connection can never *also* carry `dev`/`infra` tags (no combinable destructive surface in one connection), asserted by §9 smoke test #4. Scoping is a **security** requirement (confused-deputy mitigation against prompt-injection laundering from web-content backends), not mere ergonomics.
4. **RE/exploitation fleet NEVER on the gateway** — hard invariant; P5 asserts no RE backend appears in the gateway tool list. Spec 2's "gateway plane" must not migrate these onto the shared surface.
5. **Env-file + backup ACLs:** `icacls` owner+SYSTEM only; backups outside any git tree, restrictive ACL, retention/shred policy; **encrypt credential-bearing backups** (user already uses `.enc` for claude-swap). Backups include `~/.mcp-funnel-master.json` (the current source of truth) and `~/.codex/config.toml`.
6. **Supply-chain pinning:** exact versions for every backend (`pkg@x.y.z` / `pkg==x.y.z` / docker `@sha256:`), a version manifest, deliberate update procedure. No `@latest`.
7. **Secret hygiene:** no Authorization/env echo in logs; scrub backend spawn/stderr; `/health` returns no config/token; startup self-check **fails closed** on missing token without printing it.
8. **Run as the logon user, not elevated/SYSTEM.** ⚠️ NSSM's default service account is **LocalSystem** — the service MUST be explicitly configured (`AppEnvironmentExtra` + the *Log on* account) to run under the interactive user, else a SYSTEM-level process holds all tokens behind an unauthenticated port (privilege-escalation amplifier). No future LAN exposure without redesign (TLS + OAuth/PKCE).
9. **Breach runbook:** pre-listed token-rotation steps for the aggregation risk.

## 6. Daemon Lifecycle (Windows)

- **Service manager: NSSM** (auto-restart + ordering/readiness), Task Scheduler at-logon only as a lighter fallback. Bind `127.0.0.1:7820`, run as the user.
- **Readiness:** clients use a retry/health-gated connect; first tool call must not hit a not-ready daemon.
- **Lazy-spawn** per P0 Gate A; idle-eviction per Gate F (documented).
- **Loadout binding semantics:** loadouts are **connection-bound** via the `?tags=` baked into each client's config — there is **no live runtime loadout switch in Spec-1**; changing a loadout means editing the client's `?tags=` and **reconnecting (session restart for Claude/Codex)**. (The Spec-2 TUI later automates this.) State this so the operator isn't surprised.
- **Day-2 interim ops (Spec-1 deliverable, before the Spec-2 TUI):** documented commands/PowerShell wrappers to (a) check daemon up + port, (b) list backends and state (idle/spawned/failed), (c) restart, (d) tail logs, (e) **show which loadout/tags the current session received** (so a "missing tool" complaint is self-diagnosable without reading config). Built on 1mcp's own CLI if it exposes these; else thin wrappers.
- **Per-backend spawn-failure UX:** a single backend failing at first-use errors **only that tool**, leaving the rest of the session's gateway tools intact; cause logged. **Recovery:** define whether the next tool call auto-retries the spawn (self-healing) or the failed state is sticky until a daemon/backend restart — Spec-1 must specify and document this. Distinct from daemon-down (whole gateway unavailable; RE/local tools unaffected).

## 7. Migration Plan (phased, reversible, with overlap window)

- **P-1 — Rollback scaffolding FIRST.** One-command `restore` that reverts: all config files (`~/.claude.json`, `~/.mcp.json`, `~/.codex/config.toml`, Antigravity, `~/.mcp-funnel*.json`), **plugin enable-state** (re-enable semgrep/chrome-devtools-mcp), **funnel presence**, and **NSSM service** (stop/remove). Timestamped backups; rehearse the FULL revert once while empty.
- **P0 — Spike & gates** (§3a). Go/no-go.
- **P1 — Build gateway config + tag table** (§11): port ~32 gateway servers with **exact-pinned** versions + per-server tags; gateway starts with 0 backends resident.
- **P2 — Service** (NSSM), health + lazy verified.
- **P3 — Register (additive, non-destructive):** add gateway entry to Claude (user), Codex (toml, namespaced), Antigravity; add gateway pointer to RE-project `.mcp.json`. **Old funnel left intact.**
- **P4 — OVERLAP WINDOW:** gateway AND old funnel both live; verify per-AI tool availability, RAM, ralph smoke, namespace-clean, security smoke (§9) **while the old path still works**. Precondition: no concurrent session writing the target config (quiesce or use `claude mcp` CLI exclusively; coordinate with any parallel session). ⚠️ **Peak-RAM caveat:** during overlap both fleets can be resident — run the overlap verification in a **single low-backend session** (not the full multi-session load) so the window's peak stays within headroom on the very machine this effort is relieving.
- **P5 — Cutover (destructive, only after P4 green) — per-step exit criterion + abort trigger (any red → `restore`), each step independently recoverable:**
  1. Gut home `~/.mcp.json` → *exit:* a fresh home session lists gateway tools only; *abort if* tools missing.
  2. Disable `plugin:semgrep`, `plugin:chrome-devtools-mcp` → *exit:* `claude mcp list` shows them gone, semgrep-OSS still reachable via gateway; *abort if* semgrep scanning unavailable.
  3. Remove `mcp-funnel` → *exit:* no funnel process/config remains, gateway covers its servers; *abort if* any funnel-only tool now missing.
  4. Drop browser/`context7`/`tavily` local dupes → *exit:* one browser path (playwright + claude-in-chrome) + claude.ai remotes serve the need; *abort if* a needed tool lost.
  5. Curation diff (→ P6). A half-applied state (e.g. funnel removed but plugins still on) is itself valid and `restore`-able — steps are not all-or-nothing.
- **P6 — Final verify + curation diff:** assert no previously-disabled server silently became enabled (diff disabled/enabled sets pre/post); re-run §9 suite.
- **Live-rewrite hazard:** `~/.claude.json` is rewritten by running sessions → re-read/compare-mtime/merge-retry, prefer `claude mcp` CLI; exercised in P4 with a real second session running.

## 8. The Codex `web` namespace collision

Likely a backend exposing a `web` tool namespace clashing with Codex's built-in web tool. Fix via 1mcp **selective** per-backend namespacing (rename only the offender) — confirmed available, verified in P0 Gate D. **If uniform namespacing is the only option,** P5 adds a rename-migration: inventory every name-dependent reference (skills, `settings.json` allowedTools, ralph project config, hooks) and update them. Identify which backend currently exposes `web` during P0.

## 9. Testing / Verification (scripted, pass/fail thresholds)

- **RAM:** per-server profiler; assert typical-session steady-state **< 1.5 GB**; also record worst-case "all-warm" ceiling + idle-eviction behavior.
- **Tool availability:** scripted per-AI, per-backend probe (one representative tool asserted callable) against the §11 inventory.
- **ralph:** headless smoke (RE fleet reachable with daemon stopped → proves G3 independence).
- **Namespace:** assert Codex startup logs do **not** contain the `web collides` string.
- **Security smoke:** (1) unauthenticated request rejected; (2) forged-Origin rejected; (3) gateway tool list contains **no** RE/exploitation backend; (4) a `research` loadout **cannot** invoke github-write/digitalocean/docker/postgres; (5) grep logs + `/health` for token material after a forced backend-auth failure → none; (6) **`icacls` assertion** that the env file + backup dir grant access to owner+SYSTEM only (no Users/Everyone); (7) **NSSM service account is the interactive user, not LocalSystem**.
- **First-call latency:** cold-backend first tool call completes **< 5 s** (G2 target; the lazy-spawn tradeoff, verified not assumed).
- **Default-loadout guard:** assert the `default`/`minimal` loadout tag combination is materially **smaller than the full fleet** (does not silently re-expose "all tools" and undercut G1) — a real token/RAM gate, not a label over everything.
- **Curation preservation:** pre/post diff of disabled/enabled sets = no silent flips.
- **Rollback:** `restore` returns the machine to pre-migration state end-to-end (rehearsed P-1, re-tested P6).

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **Lazy = schema-only (RAM win fails)** | P0 Gate A measures it; fallback = Docker MCP Gateway or renegotiate G2 (mcp-proxy does NOT fix this — it's eager too). **NB for planner:** a Docker pivot is NOT a config swap — it invalidates §7 (P1-P6) and §11 (1mcp `?tags=`/namespacing) and requires a re-plan |
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
| `quality` | codacy, codecov, deepsource, qlty, sonarqube, sentry, semgrep-OSS |
| `infra` *(default-deny)* | digitalocean *(docker/postgres are LOCAL in v2)* |
| `social` | tiktok, insta-mcp, fb-messenger |

*(Exact mapping + which tags each AI/loadout requests is a P1 artifact; `minimal`/`default` map to tag combinations.)* **Frozen as a Spec-1 output contract:** the tag-table **schema/format** (server→tags[], loadout→tags[]) is locked at end of P1 so Spec 2 (TUI) consumes it without re-deriving. **Default-loadout guard:** `default` must NOT equal the full fleet (see §9) — `tooluniverse` alone exposes hundreds of tools, so the default loadout must stay a real gate, with heavy backends (tooluniverse, schrodinger) opt-in per task.

## 12. Program Roadmap (beyond Spec 1)

- **Spec 2 — `mcp-manager` TUI** (Textual): planes = Claude · Codex · **gateway** · Antigravity; loadouts = the §11 tag presets (shared deliverable from Spec 1, not re-derived). Adapts the user's mcp-manager mission (funnel plane → gateway plane). Depends on Spec 1.
- **Spec 3 — User-authored skill consolidation:** inventory user-made vs marketplace skills (marketplace untouched); dedup/merge; cross-AI distribution.
- **Closing tasks:** (a) **fix Codex `web` collision** (covered by §8); (b) **reconcile `agent-skills-toolchain` repo** to the captured final ground truth (gate on Spec 1 completion so reconciliation isn't against a moving target).

## 13. Sources

- [CC #28860](https://github.com/anthropics/claude-code/issues/28860) · mcp-funnel [#95](https://github.com/chris-schra/mcp-funnel/issues/95) / [repo](https://github.com/chris-schra/mcp-funnel)
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp.md) · [1mcp](https://github.com/1mcp-app/agent) / [docs](https://docs.1mcp.app/reference/architecture)
- [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) · [shared-daemon walkthrough](https://shyamverma.com/shared-mcp-servers-claude-code) · [Docker MCP Gateway](https://github.com/docker/mcp-gateway)