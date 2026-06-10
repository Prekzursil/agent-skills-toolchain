# Unified Cross-AI MCP Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax. **For this run the main agent executes directly (autonomous), reserving subagent adversarial review for checkpoints and the full TDD loop for the Spec-2 TUI.**

**Goal:** Replace per-session stdio MCP duplication (~8 GB/2 sessions) with one shared, lazy, authenticated 1mcp HTTP gateway reachable by Claude/Codex/Antigravity, dedup/merge ~40 servers to one logical layer + claude.ai remotes, reversibly.

**Architecture:** A single NSSM-supervised `1mcp` daemon on `127.0.0.1:7820` (bearer-token + Origin-checked), lazy-spawning shared backends behind per-connection `?tags=` loadouts; stateful RE fleet + basic-memory/postgres/docker stay LOCAL; claude.ai remotes for dupes. Spec → `docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design.md` (v2.1).

**Tech Stack:** 1mcp (`@1mcp/agent` v0.32.2, Node 25), NSSM, PowerShell 7 (orchestration/verification/rollback), Python 3.12 (per-server RAM profiler, reused), `claude mcp` CLI, tomlkit (Codex toml), Textual (Spec-2 TUI). Fallbacks: Docker MCP Gateway (if P0 Gate A fails), authenticating reverse-proxy (if Gate D1 fails).

---

## Program Decomposition (4 plans, sequenced by dependency)

| Plan | Subsystem | Status | Depends on |
|---|---|---|---|
| **THIS doc — Spec 1** | Unified gateway + dedup/merge + cross-AI registration | detailed below | — |
| Spec 2 (follow-on) | `mcp-manager` Textual TUI | outline §SPEC-2 | Spec 1 P0 answers + §11 tag-table contract |
| Spec 3 (follow-on) | User-authored skill consolidation | outline §SPEC-3 | independent; sequence after Spec 1 |
| Closing (follow-on) | Codex `web` fix + repo reconciliation | outline §CLOSING | final ground truth from Spec 1 |

**Why not fully detail 2/3 now:** Spec 2's plane-adapter and Spec 3's distribution mechanics hinge on Spec 1's *measured* outputs (does 1mcp multiplex one-shared-child? does it support bearer auth? the frozen tag-table). Writing concrete steps before P0 = placeholders. Each follow-on plan is written (via this same skill) at the moment its inputs land.

**Global execution rules (apply to every WU):**
- **Verification-as-tests:** each migration WU writes its assertion script FIRST, runs it RED against current state, performs the change, runs it GREEN. Scripts live in `D:\tools\mcp-gateway\verify\`.
- **Scoped git adds only** (`git add <path>`, never `-A`) — a parallel session has WIP; never sweep siblings.
- **Backups before every config edit**, timestamped, to `D:\tools\mcp-gateway\backups\` (ACL-locked, outside any git tree).
- **Hard-stops** (pause + report, do NOT autonomously continue): P0 Gate A fail → Docker re-plan; any OAuth/browser handoff; a live session actively writing `~/.claude.json` during a destructive step.
- **Install root `D:\tools\mcp-gateway\`** (C: is space-constrained, matching the user's `D:\tools\` convention).

---

## SPEC 1 — Work Units

### WU0 (P-1): Rollback scaffolding + backup harness — BUILT & REHEARSED FIRST

**Files:**
- Create: `D:\tools\mcp-gateway\scripts\backup.ps1`
- Create: `D:\tools\mcp-gateway\scripts\restore.ps1`
- Create: `D:\tools\mcp-gateway\verify\profiler.ps1` (per-server MCP RAM profiler — the Gate-A/G2 measurement instrument, authored here, NOT copied)
- Create: `D:\tools\mcp-gateway\backups\` (ACL: owner+SYSTEM only)
- Create: `D:\tools\mcp-gateway\state\migration-manifest.json` (records what each phase changed, for restore)

- [ ] **Step 0 — Author `profiler.ps1` (the master-gate instrument — written from scratch, not copied).** Port this session's inline forensics into a reusable script: enumerate `node/python/uv/cmd` processes, classify each to its MCP server identity by command-line regex, walk the parent chain to attribute shim layers (`cmd→uvx→python`) to the owning server and to the root client (`claude/codex`), sum `WorkingSet64` per server and per session. Output JSON + a ranked table. Accept a `-Baseline`/`-Label` arg to snapshot for before/after diffing. **Self-test:** run it now against the live machine and assert it returns a non-empty per-server table whose total ≈ the sum of current node+python working set (sanity bound). This script is consumed by Gate A (WU1), WU5.1, WU6.2, WU7.2.
  Run: `pwsh D:\tools\mcp-gateway\verify\profiler.ps1 -Label pre-migration`
  Expected: JSON written to `state\ram-pre-migration.json`; table lists semgrep/chrome/etc. with non-zero MB.

- [ ] **Step 1 — Create install tree + locked dirs.**
  Run: `New-Item -ItemType Directory -Force D:\tools\mcp-gateway\{scripts,verify,config,backups,state,logs}`
  Then lock backups + config: `icacls D:\tools\mcp-gateway\backups /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" "SYSTEM:(OI)(CI)F"` (same for `\config`).
  Expected: dirs exist; `icacls D:\tools\mcp-gateway\backups` shows only the user + SYSTEM.

- [ ] **Step 2 — Write `backup.ps1`.** Snapshots, with a timestamp label arg, ALL of: `~/.claude.json`, `~/.mcp.json`, `~/.codex/config.toml`, the Antigravity MCP config (path resolved in WU1/P0 Gate E), `~/.mcp-funnel.json`, `~/.mcp-funnel-master.json`, `~/.mcp-funnel-profiles.json`, and the current `claude plugin list` + `claude mcp list` text. Appends a manifest entry. Copies to `backups\<timestamp>\`. **Credential-bearing-backup encryption (spec §5.5):** files that contain or (post-WU4) will contain tokens — `~/.claude.json`, `~/.codex/config.toml`, Antigravity config — are encrypted at rest via **Windows DPAPI** (`[System.Security.Cryptography.ProtectedData]::Protect(..., CurrentUser)`), written as `*.json.enc`/`*.toml.enc`; `restore.ps1` decrypts with the same `CurrentUser` scope. DPAPI ties decryption to the logon user (matches the §5 trust boundary; no password to manage). Non-secret files (funnel configs, list text) stay plaintext under the ACL.

- [ ] **Step 3 — Write `restore.ps1`.** Reverts in this order, each idempotent: (a) stop+remove the NSSM `mcp-gateway` service if present; (b) copy back all config files from a chosen `<timestamp>`; (c) re-enable plugins recorded as disabled (`claude plugin enable semgrep`, `chrome-devtools-mcp`); (d) confirm `~/.mcp-funnel*.json` restored (funnel reinstated). Prints a diff summary. Supports `-DryRun`.

- [ ] **Step 4 — REHEARSE the full revert while empty.** Run `backup.ps1 -Label rehearse`; make a trivial reversible edit (e.g., add a dummy key to a copy); run `restore.ps1 -Timestamp rehearse -DryRun` then for-real; assert all 7 files byte-match the snapshot (`Get-FileHash` compare).
  Expected: hashes match; service-removal path is a no-op (none yet). **This proves G4 before any risk.**

- [ ] **Step 5 — Commit** (to a NEW infra repo or the gateway tree under git; NOT the skills repo working tree to avoid the parallel-session WIP).
  `git -C D:\tools\mcp-gateway init && git -C D:\tools\mcp-gateway add scripts/ && git -C D:\tools\mcp-gateway commit -m "feat: rollback scaffolding + backup harness (rehearsed)"`

**Acceptance:** restore returns the machine to pre-edit state, hash-verified. **Abort trigger:** if rehearsal can't reproduce byte-exact state → stop; do not proceed to any edit.

---

### WU1 (P0): Master spike — Gates A/B/C/D1/D2/E/F (THROWAWAY, gates everything)

**Files:**
- Use: `D:\tools\mcp-gateway\verify\profiler.ps1` (authored in WU0 Step 0 — the Gate-A instrument)
- Create: `D:\tools\mcp-gateway\spike\` (throwaway 1mcp install + 5-backend test config)
- Create: `D:\tools\mcp-gateway\state\P0-results.md` (the decision record)

- [ ] **Step 1 — Install 1mcp into the spike sandbox.** `npm i -g @1mcp/agent@0.32.2` (or local prefix under `spike\`). Capture `1mcp --help` and `1mcp serve --help` → record the exact flags for: port, transport (streamable-http), auth/bearer token, per-connection tags, namespacing, lazy/eager, idle-timeout. **This flag inventory drives P1.**

- [ ] **Step 2 — Gate A (MASTER): lazy = PROCESS spawn?** Configure 5 cheap stdio backends (e.g., markitdown, repomix, pdf-reader, mcp-graphql, ocr). Start `1mcp serve --port 7820`. With **0** tool calls, run `verify\profiler.ps1` → assert those 5 backends' child PIDs are **ABSENT**. Then call one tool on ONE backend → assert **only that one** spawns.
  - Expected (PASS): 0 resident at idle; 1 after 1 call.
  - **If FAIL (all 5 spawn at start) → HARD STOP.** Write `P0-results.md: Gate A FAIL → Docker MCP Gateway pivot`. Pause + report to user (this is a re-plan, per spec §10). Do NOT proceed to P1.

- [ ] **Step 3 — Gate B: sharing + multiplexing.** Start a 2nd client connection; call the same already-warm backend → assert **0** new backend procs. Record whether 1mcp uses one-shared-child or one-per-connection (inspect PIDs per connection). Write the answer to `P0-results.md` (drives §4 (M)-class decision).

- [ ] **Step 4 — Gate C: per-connection tag scoping.** Connect with `?tags=research` and `?tags=dev` simultaneously; assert disjoint tool lists.

- [ ] **Step 5 — Gate D1: transport auth.** Configure a bearer token; assert an unauthenticated request to `:7820/mcp` is rejected (401/403) and an authenticated one succeeds.
  - **If FAIL (no auth in 0.32.2):** try `npm view @1mcp/agent versions` for a version with auth; else plan a thin local token-checking reverse-proxy (record decision). If neither viable → HARD STOP (No-Go, per spec §5.1). Do NOT ship no-auth.

- [ ] **Step 6 — Gate D2: selective namespacing.** Configure two backends exposing a colliding name; assert 1mcp can prefix ONLY the offender (not rename all). Record whether selective or uniform-only (uniform → triggers §8 rename-migration in P5).

- [ ] **Step 7 — Gate E: Antigravity.** Resolve Antigravity's MCP config path/format (search `%APPDATA%`/`%LOCALAPPDATA%`/user home for antigravity/agy config). Register the spike gateway URL; assert Antigravity connects over streamable-http and lists a tool.
  - **If FAIL (stdio-only/unsupported):** record pre-committed fallback = Claude+Codex only, defer Antigravity. Not a hard stop.

- [ ] **Step 8 — Gate F: idle eviction.** Determine idle-timeout/eviction (call a backend, wait, re-profile). Record the all-warm ceiling. If never-evicts AND all-warm > 3 GB → route to Docker pivot decision (per spec §3a).

- [ ] **Step 9 — Write `P0-results.md` decision record** (every gate's measured result + the resulting parameters for P1: exact flags, auth mechanism, namespacing mode, multiplexing model, eviction policy, Antigravity verdict). **Adversarial review checkpoint:** dispatch one subagent to sanity-check the Gate-A measurement methodology (did we really prove process-deferral, not schema-deferral?).

- [ ] **Step 10 — Tear down the spike sandbox.** Keep only `P0-results.md` + `profiler.py`.

**Acceptance:** All gates PASS (or pre-committed non-blocking fallbacks chosen), decision record written + review-confirmed. **Hard-stops:** Gate A fail, Gate D1 no-auth-no-proxy.

---

### WU2 (P1): Build gateway config + frozen tag-table

**Files:**
- Create: `D:\tools\mcp-gateway\config\1mcp.config.json` (the ~32 gateway backends, exact-pinned versions, per-server tags)
- Create: `D:\tools\mcp-gateway\config\gateway.env` (ACL-locked; concrete secret values OR `${ENV}` refs per P0 finding)
- Create: `D:\tools\mcp-gateway\config\tag-table.json` (FROZEN Spec-1→Spec-2 contract: `{servers:{name:{tags:[],class:"S|I|M"}}, loadouts:{name:[tags]}}`)
- Create: `D:\tools\mcp-gateway\state\breach-runbook.md` (spec §5.9 — token-rotation runbook for the aggregation blast-radius)
- Modify: `D:\tools\mcp-gateway\state\migration-manifest.json`

- [ ] **Step 1 — Generate the gateway server list from current truth.** Source = `~/.mcp-funnel-master.json` + the User-scope servers in `~/.claude.json`, MINUS the LOCAL set (RE fleet, playwright, basic-memory, postgres, docker, codex-bridge) MINUS DROP set (mcp-funnel, browser dupes, context7, tavily). Pin every backend to an exact version (`pkg@x.y.z` / `==` / docker `@sha256`). Write `1mcp.config.json` using the P0-confirmed schema (auth, tags, namespacing-selective).

- [ ] **Step 2 — Write `tag-table.json`** per spec §11 (research/web/docs/dev/quality/infra/social), each server tagged + classed (S/I/M). Enforce at generation: destructive tags (`infra`, github-write under `dev`) form their own opt-in loadouts; `default`/`minimal` loadouts are a strict SUBSET (assert count < full fleet). Freeze the schema.

- [ ] **Step 3 — Write the verification assertion (RED first):** `verify\01-tags.ps1` asserts (a) `default` loadout tool-count < full-fleet count; (b) no loadout combines `web`/`research` with `dev`/`infra`. Run RED (no config live yet → expected fail/again-after).

- [ ] **Step 4 — Secrets:** populate `gateway.env` per P0 finding (prefer `${ENV}` indirection; if values inline, the file is already ACL-locked from WU0). Startup self-check (fail-closed on missing token, no token echo).

- [ ] **Step 5 — Write `breach-runbook.md` (spec §5.9).** Enumerate, per (I)-class gateway backend, the concrete token-rotation step (github → regenerate fine-grained PAT + update `gateway.env`; digitalocean/sentry/codacy/codecov/sonarqube/deepsource/firecrawl/scrapegraph/apify/browserstack/tavily/linear/notion/figma → each provider's revoke+reissue URL/CLI). Trigger condition: suspected `gateway.env` or `:7820` compromise → rotate ALL listed tokens + regenerate the gateway bearer token. This is the mechanical response to the single-aggregation blast-radius.

- [ ] **Step 6 — Adversarial review checkpoint + Commit** the config tree (gateway repo). Dispatch a subagent to diff `1mcp.config.json` against `mcp-funnel-master.json` for dropped/renamed servers (catch accidental omissions).

**Acceptance:** config validates; tag-table frozen; secret hygiene asserted. **Note:** if P0 chose Docker pivot, THIS WU is re-authored for Docker catalogs instead (re-plan).

---

### WU3 (P2): NSSM service (run as interactive user) + readiness + day-2 ops

**Files:**
- Create: `D:\tools\mcp-gateway\scripts\install-service.ps1`
- Create: `D:\tools\mcp-gateway\scripts\gw.ps1` (day-2 ops CLI: status/list/restart/logs/whoami-loadout)
- Create: `D:\tools\mcp-gateway\verify\sec-smoke.ps1` (security smoke suite — spec §9 tests #1-#7)
- Create: `D:\tools\mcp-gateway\verify\02-service.ps1`
- Create: `D:\tools\mcp-gateway\docs\operator-notes.md` (loadout-binding + spawn-failure recovery semantics)

- [ ] **Step 0 — Ensure NSSM is present (unstated-dep fix).** `if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) { winget install --id NSSM.NSSM -e }` (winget/scoop/choco all available on this machine — verified). *If install fails:* **fall back to the Task Scheduler path** (`Register-ScheduledTask` at-logon running `1mcp serve`, with `-RunLevel Limited` as the interactive user) and wire THAT into Step 1/Step 3 instead. `gw.ps1` abstracts over which manager is used. Gate: `Get-Command nssm` OR a registered scheduled task exists before Step 1.

- [ ] **Step 1 — `install-service.ps1`:** install NSSM service `mcp-gateway` running `1mcp serve` with the WU2 config, bound `127.0.0.1:7820`. **Set the service logon account to the interactive user (NOT LocalSystem)** (`nssm set mcp-gateway ObjectName .\$env:USERNAME <pw>` or configured per NSSM docs; Task-Scheduler fallback runs as the user by construction); set `AppStdout`/`AppStderr` → `logs\`, `AppRotateFiles 1`. Auto-restart on exit.

- [ ] **Step 2 — Readiness probe + day-2 ops.** `gw.ps1 status` polls `http://127.0.0.1:7820/health` (authed) with retry; returns up/down + port + loaded-backend list (idle/spawned/failed) + which loadout a given `?tags=` yields. Implement `restart`, `logs -Tail`, and `whoami-loadout <tags>`.

- [ ] **Step 3 — Determine + document spawn-failure recovery & loadout-binding semantics (spec §6) → `docs/operator-notes.md`.** Empirically establish (against the running daemon) whether a backend that failed its first-use spawn **auto-retries on the next tool call (self-healing)** or stays **sticky until `gw.ps1 restart`** — document the observed behavior and, if sticky, that `gw.ps1` exposes a per-backend `reset <name>`. Also document loadout semantics: loadouts are **connection-bound via `?tags=`**, there is **no live runtime switch** — changing a loadout means editing the client config and reconnecting (session restart for Claude/Codex). State both so the operator isn't surprised (the Spec-2 TUI later automates the switch).

- [ ] **Step 4 — Author `verify\sec-smoke.ps1` (spec §9 #1-#7), RED-first.** Assertions: (1) unauthenticated request to `:7820/mcp` rejected; (2) forged-`Origin` request rejected; (3) gateway tool list contains **no** RE/exploitation backend; (4) a `research`/`web` loadout **cannot** invoke github-write/digitalocean/docker/postgres; (5) grep daemon logs + `/health` for token material after a forced backend-auth failure → none; (6) `icacls` on `gateway.env` + `backups\` grants owner+SYSTEM only; (7) service/task runs as the interactive user, not LocalSystem. Run #1/#2/#6/#7 now (others depend on registered backends → run fully in WU5.1).

- [ ] **Step 5 — Verify (RED→GREEN):** `verify\02-service.ps1` asserts the daemon runs as the interactive user (`Get-CimInstance Win32_Service | ? Name -eq mcp-gateway | select StartName` ≠ LocalSystem; or the scheduled task's principal = the user), binds 7820, and unauthenticated curl is rejected. Run.

- [ ] **Step 6 — Commit.**

**Acceptance:** daemon up as the user, authenticated, day-2 ops usable, recovery+loadout semantics documented. **Security checkpoint:** `verify\sec-smoke.ps1` #1/#2/#6/#7 green.

---

### WU4 (P3): Additive registration — Claude / Codex / Antigravity / RE-project (NON-destructive)

**Files (all backed up first):**
- Modify: `~/.claude.json` (user scope: add ONE `gateway` http entry) — via `claude mcp add --scope user --transport http gateway http://127.0.0.1:7820/mcp --header "Authorization: Bearer ${...}"`
- Modify: `~/.codex/config.toml` (add `[mcp_servers.gateway]` url, via tomlkit, validate with tomllib)
- Modify: Antigravity config (add gateway URL; skip if Gate E failed)
- Modify: RE-project `.mcp.json` (`D:\ReverseTools\Android\battlecats-toolkit\.mcp.json`) — add gateway pointer alongside the existing RE fleet (for ralph)

- [ ] **Step 1 — `backup.ps1 -Label P3`.**
- [ ] **Step 2 — Register gateway in each client** using the commands above; **old funnel left fully intact** (additive only).
- [ ] **Step 3 — Verify (RED→GREEN):** `verify\03-register.ps1` asserts each AI lists the gateway connection (`claude mcp list` shows gateway connected; `codex mcp list --json` includes it; Antigravity if applicable). Codex startup log free of `web collides` (Gate-D2 namespacing applied).
- [ ] **Step 4 — Commit** the gateway-repo manifest update (NOT the user configs — those are backed up, not git-tracked here).

**Acceptance:** all targeted AIs see the gateway; funnel still works. **Hard-stop:** if a live session is writing `~/.claude.json` (mtime changes mid-edit) → use `claude mcp` CLI only / quiesce / pause.

---

### WU5 (P4): Overlap-window verification (both paths live)

- [ ] **Step 1 — Single low-backend session** (peak-RAM caveat): with gateway AND funnel both registered, run the full `verify\` suite: per-AI tool availability (`verify\04-availability.ps1` probes one representative tool per gateway backend), RAM (`profiler.py` → assert typical < 1.5 GB), `verify\sec-smoke.ps1` #1-#7, `verify\01-tags.ps1` GREEN, first-call latency < 5 s.
- [ ] **Step 2 — ralph smoke:** stop the gateway daemon; assert the RE fleet is still reachable from a project-scope session (`verify\05-ralph.ps1`) — proves G3 daemon-independence. Restart daemon.
- [ ] **Step 3 — Live-rewrite test:** with a 2nd real Claude session running, exercise a `claude mcp` CLI edit; assert no lost update (mtime-merge-retry path).
- [ ] **Step 4 — Adversarial review checkpoint:** dispatch a subagent (fresh) to audit the verify results + look for gaps before the destructive phase. **GO/NO-GO for P5.**

**Acceptance:** all green in the overlap window. **Abort:** any red → `restore.ps1 -Timestamp P3`; do not enter P5.

---

### WU6 (P5): Destructive cutover — per-step, each independently recoverable

(Each step: `backup.ps1 -Label P5-stepN` → change → step verify → if red `restore`.)

- [ ] **Step 1 — Gut home `~/.mcp.json`** (reduce to empty/minimal). *Exit:* fresh home session lists gateway tools only. *Abort if* tools missing.
- [ ] **Step 2 — Disable `plugin:semgrep`, `plugin:chrome-devtools-mcp`** (`claude plugin disable ...`). *Exit:* gone from `claude mcp list`; semgrep-OSS reachable via gateway; **measure RAM drop** (expect ~-1 GB from semgrep Pro). *Abort if* semgrep scanning unavailable.
- [ ] **Step 3 — Remove `mcp-funnel`** from all configs. *Exit:* no funnel proc/config; gateway covers its servers. *Abort if* a funnel-only tool missing.
- [ ] **Step 4 — Drop browser/`context7`/`tavily` local dupes.** *Exit:* one browser path + claude.ai remotes serve the need. *Abort if* a needed tool lost.

**Acceptance:** each step green; half-applied states are valid + restorable. **Hard-stop:** live-config-write race.

---

### WU7 (P6): Final verify + curation diff + RAM proof

- [ ] **Step 1 — Curation diff:** `verify\06-curation.ps1` diffs the pre-migration vs post disabled/enabled server sets → assert no SILENT enable/disable flips (only the intended ones).
- [ ] **Step 2 — Full RAM remeasure** across 2 real sessions via `profiler.py` → assert typical < 1.5 GB, record all-warm ceiling < 3 GB. **This is the headline G2 proof.**
- [ ] **Step 3 — Re-run the entire `verify\` suite** GREEN; re-test `restore.ps1` end-to-end (P6 rehearsal).
- [ ] **Step 4 — Capture final ground truth** → `D:\tools\mcp-gateway\state\FINAL-STATE.md` (feeds the closing repo reconciliation). Commit.

- [ ] **Step 5 — CONTINUATION TRIGGER (so "everything to the end" doesn't stop at WU7).** With Spec 1's outputs now real (P0-results.md = multiplexing/auth answers; frozen `tag-table.json`; `FINAL-STATE.md`), **immediately invoke `superpowers:writing-plans` to author the Spec-2 plan** (mcp-manager TUI) using those inputs, run it through the Plan Review Gate, then execute it; then Spec-3 (skill consolidation); then CLOSING (Codex `web` confirm + repo reconciliation + `/self-reflect` knowledge capture before the PR). Each follow-on plan is authored only once its inputs exist (per the §Program Decomposition rationale). This step is the explicit hand-off that keeps the autonomous run going to the true end.

**Acceptance:** G1-G6 all measurably met **and** the Spec-2 plan has been authored+gated+started (or a hard-stop reported).

---

## SPEC-2 (outline — detail after Spec 1 P0/§11 land): `mcp-manager` Textual TUI

Per the user's mcp-manager mission, **adapted**: control planes = Claude · Codex · **gateway** · Antigravity (funnel plane → gateway plane). Loadouts = the FROZEN `tag-table.json` contract. Core + plane adapters + thin Textual UI; full **TDD** (this is the real app — RED/GREEN per adapter, mocked CLI output + temp config fixtures, coverage gate per `.coverage-thresholds.json`). Install `D:\tools\mcp-manager\`, `uv run`, `/mcp-gui` slash command + PATH shim. **Dependency:** needs P0's multiplexing/auth answers + the frozen tag-table; written via writing-plans once those exist.

## SPEC-3 (outline): User-authored skill consolidation (cross-AI)

Inventory user-made skills (in `~/source/agent-skills-toolchain/skills` + `~/.agents/skills`) vs marketplace (plugin cache — **never touch, they auto-update**). Dedup/merge similar user skills; ensure cross-AI distribution (Claude `~/.claude/skills`, Codex, Antigravity, `~/.agents/skills` per the toolchain's copy-not-symlink manifest). Independent of Spec 1; sequence after. Written via writing-plans when started.

## CLOSING (outline): Codex `web` fix + repo reconciliation

- **Codex `web` collision:** root-caused + fixed structurally by Spec-1 P0 Gate D2 (selective namespacing of the offending backend). Closing task = confirm fixed + document which backend exposed `web`.
- **Repo reconciliation:** update `agent-skills-toolchain` to the `FINAL-STATE.md` ground truth — refactor/document/trim/clear stale MCP+skill docs, the new gateway architecture, mcp-manager. **Gate on Spec 1 completion** (reconcile against the real final state, not a moving target). Then `/self-reflect` + commit knowledge-base updates BEFORE the PR (per CLAUDE.md pre-PR knowledge capture).

---

## Self-Review

- **Spec coverage:** G1 (availability) → WU4/WU5/WU7 probes; G2 (RAM) → WU1 Gate A + WU6.2 + WU7.2; G3 (ralph) → WU5.2; G4 (reversible) → WU0 + per-step backups + WU7.3; G5 (`web`) → WU1 Gate D2 + CLOSING; G6 (auth/scoping) → WU1 D1 + WU2/WU3 + sec-smoke. §3a gates → WU1. §4 disposition → WU2.1. §5 security → WU2/WU3 + sec-smoke. §7 phases → WU0-WU7 1:1. §11 tag-table → WU2.2. All covered.
- **Placeholder scan:** P0-dependent params (exact 1mcp flags, auth mechanism) are explicitly *resolved in WU1 and recorded in P0-results.md* — not placeholders but gated unknowns with a named resolution step. Specs 2/3/closing are outlines by design (inputs don't exist yet), flagged as "detail via writing-plans when inputs land."
- **Consistency:** `tag-table.json` schema defined in WU2.2 and consumed by Spec-2; `restore.ps1`/`backup.ps1` names consistent WU0→WU6; port 7820 throughout; verify scripts numbered 01-06 + sec-smoke consistently.
- **Contingency:** Gate-A-fail → Docker re-plan (WU1.2, WU2 note); Gate-D1-fail → reverse-proxy/version-pin/No-Go (WU1.5); Gate-E-fail → Claude+Codex only (WU1.7); NSSM-absent → Task Scheduler fallback (WU3.0). Hard-stops enumerated globally + per-WU.
- **Plan-review round-1 fixes (applied):** (1) profiler is now AUTHORED in WU0 Step 0 (`verify\profiler.ps1`), not "copied"; (2) NSSM install/verify + Task-Scheduler fallback added (WU3 Step 0); (3) spawn-failure recovery + loadout-binding semantics documented (WU3 Step 3 → `operator-notes.md`); (4) breach runbook added (WU2 Step 5 → `state/breach-runbook.md`); (5) credential-bearing backups DPAPI-encrypted (WU0 Step 2); (6) `sec-smoke.ps1` now has an explicit RED-first authoring step (WU3 Step 4); (7) continuation trigger added so the autonomous run authors+executes Specs 2/3/closing (WU7 Step 5).
