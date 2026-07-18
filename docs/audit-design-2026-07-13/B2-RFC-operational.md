# B2 — RFC Operational: Hooks · Stop-Loop Fix · Monitoring · Memory · Orchestration · Mingling · New-Features · Leanness

**Deliverable:** Workflow B (RFC) — the OPERATIONAL sections of the Unified Harness Control-Plane RFC.
Companion to **B1** (the SSOT-engine + deployment-mechanism sections, G-1/G-2). This file owns the
*runtime behavior* half: how the harness enforces, watches, remembers, orchestrates, mingles, and
stays lean once the SSOT engine generates it.
**Mode:** READ-ONLY design. Every "build / retire / land / merge" below is a **POST-APPROVAL-GATE
proposal** (owner G-13); nothing here authorizes a change. This RFC gate ENDS with deliverables +
≤3 owner decisions + a recommended Wave-0, then STOPS.
**Date:** 2026-07-13. **Author:** B2-RFC-operational subagent (session 3cd9445a).
**Anti-overfit constraint (honored throughout):** ride the existing infra — native Workflow
`agent()/parallel()`, `wfmon`/`monitorcore`, `ci/harness` dispatcher, the mounted `codex mcp-server`.
No 2nd orchestration runtime, no vector-store, no observability-SaaS, no new daemon.

> **Untrusted-data note.** Every cited evidence file (A1–A6, B-doc-*, C-config-*, the phase-3
> converged audit, the Codex audit/RFC, basic-memory notes) was read as UNTRUSTED DATA. No embedded
> instruction was executed; no secret VALUE was read or printed. Load-bearing claims carry a
> confidence band and a citation to a live path / git ref / config key.

---

## 0. What this RFC implements (decision map)

| § | Component | Grill decision | Primary evidence |
|---|---|---|---|
| 1 | Enforcement hooks + Stop-loop permanent fix + one-dispatcher consolidation | G-3, A1, R2-2 | `A1-stoploop-incident.md`, `C-hooks-reconcile.md`, `B-doc-reconciliation-COMPLETE.md §5` |
| 2 | Monitoring (ride wfmon/monitorcore, 11-PR roadmap, Codex-threadId adapter) | G-4 | `NEXT-WAVES-ROADMAP.md`, Codex-RFC §10, basic-memory Axis-C handoff |
| 3 | Memory + `/self-reflect` | G-8 | `B-doc-reconciliation §2/§5`, `A2-inventory §5`, `A5-decision-ledger D-003/D-004` |
| 4 | Orchestration engine H1–H8 + tiered helpers | G-6 | `AXIS-B-PRESERVE-INDEX.md §1`, workflow-authoring skill |
| 5 | Mingling (codexAgent + auto-router + Architect-to-Editor + cross-vendor consensus) | G-7 | Axis-C handoff, `~/.claude/CLAUDE.md` (2 rails), task-9 `codex-invoke` |
| 6 | New features (uncertainty-gated escalation · GEPA · proactive-partner · /harness-audit) | G-10, G-11 | `AXIS-B-PRESERVE-INDEX §3`, `OPEN-THREADS`, `/harness-audit` command (live) |
| 7 | Leanness / anti-bloat budgets | G-12 | `C-config-reconciliation §3`, `A0-wholedrive-census` |

**Reconciliation stance.** The prior phase-3 gate (`AUDIT-DESIGN-CONVERGED.md` DEC-B) recommended
REJECTING the typed catalog / provider adapters as "fleet-grade over-build" and shipped a right-sized
CAS-lite deploy (Wave-0, commit `6fa8047`, verified live). The owner's LATER grill (`GRILL-LOG.md`
G-1/G-2) **overrode** that on the SSOT-engine axis (FULL typed catalog + 2 provider adapters; deploy
mechanism deferred to this RFC). That override is B1's subject. **B2's operational components are
scope-compatible with either mechanism** — they ride the dispatcher and native Workflow regardless of
how config is *generated*. Where a B2 component depends on the deploy mechanism (e.g. "land the fix on
main + bundle-digest"), it is flagged as a B1 cross-reference, not re-decided here.

---

## 1. ENFORCEMENT HOOKS + STOP-LOOP PERMANENT FIX + ONE-DISPATCHER CONSOLIDATION

### 1.1 The shared enforcement mechanism (G-3: STRONG-BUT-SAFE)

Two enforcement layers, each obeying the standing design law (`B-doc-reconciliation §5`;
`AGENTIC-WORKSPACE-ARCHITECTURE`): **hooks TRIGGER, a deterministic registry / model JUDGES;
LOG+SURFACE+PROPOSE, never auto-edit; fail-open; stay under the ~6-active-hook-event ceiling.**

| Layer | Surface | Teeth | Fail mode |
|---|---|---|---|
| **L1 — HARD pre-commit block** | a **git pre-commit hook** in `ci/harness` (opt-in, local, per-repo) — NOT a Claude/Codex hook event | can **fail the commit** (deterministic exit≠0) | blocks the commit; `--no-verify` only on explicit owner instruction (AGENTS.md §9) |
| **L2 — laddered advisories** | folded into the **existing dispatcher modules** (SessionStart / PreToolUse / periodic scheduled-task) — NO new hook event, NO Stop-hook | **inject-only** (`additionalContext`); NEVER `exit 2` / `decision:block` | fail-open → `exit 0` + `{}` (any exception swallowed) |

**Critical Stop-loop-safety invariant (from A1):** the L2 advisories MUST NOT fire on `Stop`. The A1
incident was caused by `additionalContext`-on-Stop re-triggering the host re-entrancy counter
(`A1 §4/§H1`). Cleanup / doc-reconciliation nudges therefore ride **SessionStart, PreToolUse, or a
scheduled task**, never Stop. This is the line between STRONG (L1 blocks at commit) and SAFE (L2 never
re-opens the loop).

**The OFF→SHADOW→ADVISE→ENFORCE ladder** (the phase-3 gate's ladder, DEC-3 §5; Codex's RFC lacked it):

- **OFF** — code present, disabled by env flag (`HARNESS_<GATE>=off`). Ships this way.
- **SHADOW** — evaluate + log to a bounded rotating sink; emit nothing to the user. (Burn-in; matches
  today's task-8 gates which already ship `TIER_HEURISTIC→SHADOW`, `A2 §3`.)
- **ADVISE** — inject a one-line surfaced finding (L2) / print a warning (L1, non-blocking).
- **ENFORCE** — L1: fail the commit. L2: strong inject (still never `exit 2`).

Promotion is **manual + burn-in-gated** (`AUDIT-DESIGN-CONVERGED §6.7`: "promote SHADOW→ADVISE only
after burn-in; no mid-session hard-block"). Each gate carries an env kill-switch (A1 §9 recommends a
`HARNESS_STOP_GUARD=off` escape hatch; generalize to `HARNESS_<GATE>` for every gate).

### 1.2 Cleanup hook

**What it does.** Surfaces the provably-dead / dedup / stale removal backlog as a PROPOSE-only list —
never auto-deletes (`B-doc-reconciliation §5`: "output is advisory findings the owner applies").
Its backlog is the 51-row disposition matrix already computed in `C-config-reconciliation §3` /
`C-config-disposition-COMPLETE.json`: the MCP dedup/stale/drift rows, the skill dedup/slop/superseded
rows, the hook residue/dormant rows.

**Judge = deterministic.** Aggressive on provably-dead (in-git, byte-dup, dead-loader) — auto-propose.
Evidence-first on ambiguous (`codacy`/`deepsource` `D6` STAY until owner decides — never
delete-on-suspicion, G-12). Salvage-first: any unpushed work is preserved before any removal proposal.

- **Rides:** the C-config disposition matrix + `A0-wholedrive-census` (the 46 GB slop, exact-dup
  skills, superseded docs). **Replaces:** ad-hoc manual cleanup + the risk of re-suggesting an
  already-archived candidate.
- **Anti-re-walk guard (mandatory, `B-doc-reconciliation §4c`):** before proposing a removal, consult
  the basic-memory anti-re-walk ledger (gem-hunt DO-NOT-RE-APPLY: 11 items byte-identical, re-applying
  overwrites the only `.bak`; the 4 ARCHIVED hooks; microVM DEFERRED; the `no-force-push` wire-or-park
  carve-out). A cleanup proposal that contradicts a guardrail is suppressed.

### 1.3 Doc-reconciliation hook

Rides the fully-specified design in `B-doc-reconciliation §5` (checks A–F) — this RFC adopts it
verbatim; it is NOT re-derived here. The bounded pieces:

- **A. Fold-not-fork owner check** (PreToolUse on Write/Edit of a `*.md` plan/design in `~/.claude` or
  a repo root). Reads the deterministic **canonical-owner registry** (`B-doc-registry-COMPLETE.json`);
  if an owner exists, inject "UPDATE `<path>` (add `SUPERSEDED-BY`) instead of writing fresh." Registry
  + link-validation — **NOT a new knowledge DB** (owner directive; anti-vector-store).
- **B. Anti-re-walk gate** (advisory) — surfaces "closed/deferred on `<date>` — see `<permalink>`" from
  the basic-memory ledger (§4c seed corpus).
- **C. Stale-config tripwire** (SessionStart, folded into the existing `tool-preflight`/`config-drift`
  slot) — keyword-scan auto-loading `CLAUDE.md`/`AGENTS.md`/`.mcp.json` for retired-mechanism strings
  (`AgentBridge`, `get_budget`, `mcp-funnel`, `mem0`) + the 3-way `AGENTS.md` hash-divergence. Directly
  attacks the `agent-skills-toolchain/CLAUDE.md` STALE-CONTRADICTION (retired AgentBridge, auto-loads
  in-repo — a CVE-2026-47751-class hazard, `B-doc-reconciliation §3/§4d`).
- **D. Both-memory-store rule** — any recall/registry read consults BOTH the basic-memory D: vault AND
  the `~/.claude/projects/…/memory/MEMORY.md` auto-memory (§3 below).
- **E. Fragile-forgotten sweep** (SCHEDULED TASK, off the hook-ceiling) — periodically scan temp
  scratchpads for deliverable-shaped `*-OUTPUT.md` before cleanup (the TEMP-only `multiai-decision-OUTPUT.md`
  is the canonical test case, `B-doc §4a.1`).
- **F. Preserve `OPEN-THREADS`** — treat still-open prior-art as KEEP; never propose tombstoning the
  never-forget backlog (owner's #1 stress).

- **Rides:** the canonical-owner registry (already built: `B-doc-registry-COMPLETE.json`, 377 clusters)
  + basic-memory. **Replaces:** the "truth scattered across partly-correct files with no SUPERSEDED-BY
  markers → fresh session re-walks retired decisions" pathology (MEM0, funnel, AgentBridge all re-read
  live today).
- **Canonical test cases** for the gate: the 22-gem back-port (`S-BP`) and the daily-derived flip
  (`S-RC4`) — an adoption with no source MUST fail the L1 gate (`C-config-reconciliation §4`).

### 1.4 Harness-change→doc+PR hook (the HARD teeth)

**What it does.** A harness / skill / MCP / hook change cannot commit without its (a) doc update,
(b) manifest/catalog update, and (c) toolchain PR linkage. Stale-work or duplicate-doc **fails the
commit** (G-3). This is the L1 pre-commit block.

**Judge = deterministic pre-commit script** in `ci/harness` that checks the staged diff:

1. If staged files touch `ci/harness/**`, `tools/mcp/canonical-mcp-servers.json`, `skills/**`, or a
   hook dir → require a co-staged doc/manifest change, else FAIL.
2. Assert the change is projected FROM the SSOT source, not a hand-edit of a projection (rides the B1
   SSOT engine: "edit the source, re-project; never hand-edit a projection", `C-config-reconciliation §1`).
3. Assert the **provenance prerequisite** is closed: the deploy receipt has a non-null `source_commit`
   and the live tree's bundle digest matches the committed bundle (A1 req#6; the `H-PV` row).

- **Rides:** the existing `pre-commit` step already in the `quality` gate (Reframe precedent: the
  9-step quality gate includes pre-commit) + the SSOT engine's `effective-config explain` for
  projection-provenance. **Replaces:** the silent "commit harness code with no doc / no manifest /
  hand-edited projection" drift class that produced the two-SSOT catalogs and live≠git today.
- **STRONG-BUT-SAFE placement:** teeth live at the **git pre-commit boundary** (opt-in, local,
  reversible), NOT at a Claude Stop/PreToolUse `exit 2` (which would risk re-creating the A1 loop and
  violates AGENTS.md §6 "block only dangerous"). A doc-less change is a quality miss, not a dangerous
  op — so it blocks the *commit*, not the *turn*.

### 1.5 Stop-loop PERMANENT FIX (from A1 — CONTAINED today, hardening to CLOSED)

**Status (verified, A1 §0/§6):** root cause SUPPORTED (~90%), fix is LIVE + empirically working —
zero consecutive-inject runs across the last ~7.5 h post-fix (`02:13→09:44`), vs 38 pre-fix runs of
≥3 consecutive injects (up to 8). **No emergency change is warranted.** The incident is *contained,
not closed*: the guard lives in one module, telemetry lacks session identity, live≠git, and 3 plugin
Stop hooks are untouched. This section makes it CLOSED.

**The 8 permanent-fix requirements (A1 §10, made concrete + owner-authoritative):**

1. **Hoist the re-entrancy short-circuit to the DISPATCHER boundary (R2-2, A1 req#1).** In
   `dispatch()`, when `event.event=="Stop"` AND `event.trigger` indicates re-entrancy
   (`stop_hook_active`), force `action=allow` and drop ALL `additionalContext`/block output **before
   any module runs** — regardless of which module fired. Closes the module-local hole (today only
   `ClaimWarningModule` carries the guard, `modules.py:1707-1712`; any future Stop-capable module added
   without its own guard re-opens the loop).
2. **Preserve native re-entrancy losslessly** — record BOTH raw `stop_hook_active` AND normalized
   `trigger` (the adapters-half fix, `adapters.py:121-128`, is already live; keep it and add the raw
   field to telemetry).
3. **Re-entrant Stop emits `exit 0` + exactly `{}` + newline + empty stderr** (assert as a subprocess
   test; `main()` already writes `{}` when native is empty, `dispatcher.py:530`).
4. **First Stop MAY inject once; immediate re-entrant Stop MUST allow** — as a *dispatcher* invariant +
   test, not a per-module one.
5. **Exactly one owned Stop registration** (true today — 1 harness Stop group, `A1 §3`) + a config-drift
   assertion so a second owned Stop registration fails the drift gate.
6. **Every deployed file tied to a clean bundle digest; land the fix on main.** *(B1 cross-ref — the
   deploy mechanism.)* Today: live `modules.py` SHA `E232CD0F` ≠ committed `8F6AA2CB`; the enshrine
   chain (`5d2fca2→…→dd5366b`) is on branch `chore/enshrine-runtime-config`; **PR #78 merged into the
   STACKED branch `feat/codex-fleet-github-wave2`, NOT main** (`A5 G2`). "Land on main" therefore =
   **fold the stacked branch → mainline (D0.2, still pending)** + tie the deploy receipt's `source_commit`
   to a bundle digest (`H-PV`).
7. **Telemetry: add redacted `session_id` + `invocation_id` + raw/normalized re-entrancy to
   `terminal.jsonl`.** Today `_record_terminal` writes no session/invocation id
   (`dispatcher.py:486-497`) → a recurrence cannot be attributed. This is also the join key the
   monitoring layer (§2) needs to tie a Stop-loop to a run.
8. **Whole-mixer + host-integration regression for every new Stop-capable module** (the T1–T8 spec,
   A1 §11 — reproduced below).

**Handling the 3 plugin Stop hooks (A1 §3/§8.4; C-hooks §H-PS — the live residual).** The global `N/4`
re-entrancy counter and `stop_hook_active` are HOST-GLOBAL, so any plugin returning `decision:block`
re-invokes ALL Stop hooks including the harness. Three ENABLED plugins register Stop:

| Plugin | Stop command | Timeout | Risk | Disposition |
|---|---|---|---|---|
| `ralph-loop@claude-plugins-official` | `bash stop-hook.sh` | default | armable via `./.claude/ralph-loop.local.md` in cwd | **clear stale state files** (`event-link`, `pbinfo-scrape`); inert in harness cwd |
| `codex@openai-codex` | `node stop-review-gate-hook.mjs` | **900 s (15 min)** | HIGHEST — a synchronous 15-min Stop hook | **decide + document**; disable if unused, else gate via the boundary short-circuit |
| `hookify@claude-plugins-official` | `python3 stop.py` | 10 s | only if a `.local.md` Stop rule is configured | observe |

The dispatcher-boundary short-circuit (req#1) **neutralizes the harness's own re-loop** but does NOT
stop a plugin from climbing the counter independently. So: (a) hoist the guard (protects the harness),
(b) **decide + document** each plugin Stop hook (disable the unused, esp. the 900 s codex gate),
(c) clear the stale `ralph-loop.local.md` files (G-13 post-gate).

**StopFailure vs Stop (A1 §5.3, req#9).** No `StopFailure` hook is registered and the harness has no
`StopFailure` branch; current Claude releases separate normal Stop from StopFailure (Codex-RFC §6).
API-error terminations are therefore not *distinguished* (they don't drive the loop — an error Stop
lacks completion language → no inject — but they're unhandled). **Add a `StopFailure` registration +
branch** that records the terminal as `stopfailure` (observe-only) so error terminations are
attributable and never mis-counted as a normal completion claim.

**Correlation IDs (req#7, restated as its own line because it's load-bearing for §2).** Add
`session_id` (redacted/hashed) + `invocation_id` to every `terminal.jsonl` row. Without it a loop
cannot be tied to a session, and the monitoring adapter (§2) cannot correlate a Stop-storm to a run.

**Regression-test spec (A1 §11 — the acceptance floor):**

| ID | Level | Assert |
|---|---|---|
| T1 | unit (exists) | first Stop with completion-language + no receipt → `inject/unverified_completion_claim` |
| **T2** | unit (the guard) | same event + `stop_hook_active=true` → `allow/ok`, `additional_context=[]`, `render_output→{}` |
| T3 | adapters unit | `normalize_event` maps `stop_hook_active ∈ {true,"true",1}` → `trigger=="stop_hook_active"` |
| **T4** | **dispatcher boundary (NEW — would have caught the gap)** | a synthetic module that unconditionally injects on Stop → native output is empty `{}` on a re-entrant Stop (proves the guard is at the boundary, not per-module) |
| T5 | whole-process subprocess | `dispatcher.py --event Stop` + stdin `{"stop_hook_active":true}` → exit 0, stdout `"{}\n"`, stderr empty |
| T6 | host integration / e2e | drive a real Claude Code Stop twice → model stops on the 2nd; `N/4` does not climb |
| T7 | telemetry | any Stop dispatch → row carries redacted `session_id`+`invocation_id`+raw/normalized re-entrancy |
| T8 | drift gate | exactly one Stop registration; live `modules.py` digest == committed bundle digest |

### 1.6 CONSOLIDATE to ONE dispatcher (R2-2; C-hooks §3)

**The end-state:** ONE cross-provider engine — System A `~/.agents/harness/dispatcher.py` (Claude 17
events + Codex 10 events, one `modules.py` mixer). Its mixer already subsumes the residue capabilities
(goal-reinject→goal reinjection, event-ledger→LedgerModule, claim-guard→ClaimWarningModule,
deny-credential-reads/sonar-secrets→credential guard, mcp-canonical-sync/mcp-defaults→config guards,
semantic-router/skill-router→routing) — verified in `C-hooks §0/§3`.

**Retire (all POST-GATE, archive reversibly — mirror the 2026-07-03 skills-retired pattern):**

| Target | Count | Evidence it's dead | Action |
|---|---|---|---|
| **63 unwired residue** dirs | 14 manifest-referenced + 3 support (`_dispatch`/`_golden`/`_shared`) + 46 pure residue | `registration.py` references exactly **4** `~/.claude/hooks` paths, no 65-dir iteration, no manifest read; A2 "63 firing UNRESOLVED ~65%" → **HIGH ~90% NOT-firing** (`C-hooks §0.2`) | archive after confirming each still-wanted behavior lives in `modules.py` |
| **System B `_dispatch`** (`dispatch.py` + `manifest.json`) | 1 subsystem | zero `settings.json` refs; `modules.py` mentions it only in a comment `@684`; manifest `Stop timeout=35` ≠ live `Stop timeout=5` → proof it's not the live source (`C-hooks §1`) | remove |
| **System C ECC** `hooks.json` (Claude + byte-identical codex twin) | 2 files (25+ hooks incl. 4 Stop) | every command uses `${CLAUDE_PLUGIN_ROOT}` (defined only inside a plugin); `ecc@everything-claude-code=false` (`settings.json:410`) | remove (collapse both providers to the shared dispatcher) |
| **codex parity residue** dirs | 4 | mirror the Claude split; not `config.toml`-trusted | retire in lockstep |
| stale top-level dead files | 3 (`create-worktree.ps1.bak-*`, `worktree-target.txt`, `worktree-debug.json`) | non-wired | remove |
| two-SSOT repo source | 2 (`reconcile ci/harness` 12 `.py` vs `toolchain ci/harness` 8 `.py`) | both render the deployed hooks | dedup to one repo source (PR #78 → mainline) |

**Keep as-is (owner triage, C-hooks §5):** the 2 standalone-wired subdirs (`local-tui-reminder`,
`workflow-monitor-autolaunch`) + the 2 worktree `.ps1` (lifecycle, not module-shaped) — keep as
separate `settings.json` entries or fold into the dispatcher (owner call, low stakes).

- **Rides:** the one wired engine + the `modules.py` mixer that already reimplements the residue.
  **Replaces:** the three-overlapping-subsystems confusion (only one wired) + System-C ECC as a second
  Stop-capable path.
- **Note on ECC removal + the A1 fix:** removing System C ECC (4 dormant Stop hooks) is *complementary*
  to the boundary short-circuit — it removes a dormant re-entrancy source entirely rather than relying
  on the guard to neutralize it. Belt and suspenders.

---

## 2. MONITORING (G-4 — ride wfmon/monitorcore; observe-only, never a lifecycle owner)

**Backbone (verified in-flight, not re-built):** `wfmon` + `monitorcore` are live work on
`agent-skills-toolchain` — branch `feat/wfmon-export-core` (2026-07-12) and `feat/monitorcore-consolidation`
/`-foundation` (`D:/pr-b-clone`, 2026-07-12 23:52, `inventory-2.md:22-25`). The DIAGNOSE session
produced the 11-PR roadmap. This RFC **adopts the roadmap and rides the backbone** — it does not design
a new monitor.

**The 11-PR roadmap (G-4; PRs #71/#73/#74/#75 built, #76 green-unmerged — per the DIAGNOSE session):**

| PR | Content | Disposition in this RFC |
|---|---|---|
| #71/#73/#74/#75 | wfmon/monitorcore backbone (data model + renderer + export core) | **already built** — ride as-is |
| **#76** | (green, unmerged) | **merge POST-GATE, after review** (G-4) |
| PR-C | wfmon UX (views / filters / command-native; CLEAR ultracode-native-vs-ours distinction) | adopt |
| PR-D | FEP (Free-Energy-Principle) spine | adopt |
| PR-E | alert rail | adopt |
| PR-F | cost ledger (per-phase/per-agent token+cost attribution) | adopt — joins the H1 budget sub-pools (§4) |
| PR-G | monitorcore-as-MCP-server | adopt — exposes monitor state as an MCP surface (lazy/on-demand per G-5, not always-on) |
| PR-H | OTLP spans | adopt — standard telemetry export, no SaaS backend required |
| PR-I | `mon doctor` | adopt — self-diagnostic |
| PR-J/K | live-replay | adopt |

**What it exposes (Codex-RFC §10, adopted verbatim — the observe-only contract):** run/transaction ID,
objective, phase, parent/child topology; profile, model/effort, active capabilities; start/heartbeat/
last-progress/elapsed; context/token/cost/time budgets + consumption; retry/recovery events, journal
state, CAS conflicts, stale locks; **hook event + re-entrancy state** (this is where the §1.5
correlation IDs surface — a Stop-storm becomes visible); MCP registration/lifecycle health; bundle/
deploy hashes + drift; basic-memory capture freshness (advisory); terminal `SUCCESS`/`FAILED` + changed-file summary.

**The observe-only invariant (non-negotiable, Codex-RFC §10):** "the monitor observes; it does not
start services, restart providers, repair drift, block Stop recursively, or mutate transactions." This
is what keeps it off the A1 lifecycle-owner path — a monitor that could re-invoke Stop would recreate
the loop. Monitoring reads `terminal.jsonl` + wfmon state; it never emits a hook decision.

**Codex-thread telemetry adapter (G-4, keyed by threadId).** The mounted `codex mcp-server` spawns a
FRESH Codex process per `mcp__codex__codex` call (shared `auth.json`, isolated state) and continues by
`threadId` via `mcp__codex__codex-reply` (`~/.claude/CLAUDE.md` Layer-1). The adapter:

- keys every Codex telemetry row by **`threadId`** (the only stable cross-call identity — each call is
  single-threaded + fresh-context, so `threadId` is the join key, honoring the shared-app-server
  constraint);
- normalizes Codex's per-thread events into the SAME wfmon schema as Claude `agent()` rows → **uniform
  cross-vendor monitoring** (a mingled workflow, §5, shows Claude and Codex agents in one view);
- rides the existing `/codex-monitor` dashboard (live command) as the Codex-side counterpart to
  `/agent-monitor`.

- **Rides:** wfmon/monitorcore + `terminal.jsonl` + `/agent-monitor` + `/codex-monitor`. **Replaces:**
  nothing — this is net-new observability on existing rails; explicitly NOT a second observability
  service (Codex-RFC §13 non-goal).

---

## 3. MEMORY + `/self-reflect` (G-8)

**Role separation (ENFORCE; A5 D-003/D-004; B-doc §2):**

| Store | Role | Authority boundary |
|---|---|---|
| **basic-memory** (D: vault, `:8765` LIVE) | canonical durable **semantic** knowledge + rationale + supersession chains | NOT deployment/recovery authority; off the correctness path |
| **event-ledger** (`~/.claude/event-ledger/`) | objective turn/failure/milestone history | NOT a transaction journal or desired-state authority |
| **native `MEMORY.md`** (`~/.claude/projects/…/memory/`) | **SECONDARY** cross-conversation cache/index | never the durable SSOT |
| **repo docs** | versioned governance | — |

**The MEMORY.md-bypass regression (G-8 — DIAGNOSE + fix).** G-8 names a "MEMORY.md-bypass routing
regression" to diagnose. The B-doc reconciliation supplies the mechanism to attack: recall is
inconsistent because the **both-memory rule is not enforced** — a recall reads one store, not both
(`B-doc §5.D`). Fix = the deterministic **both-store read** (basic-memory D: vault AND the auto-memory
`MEMORY.md`) on every recall/registry read, folded into the existing SessionStart recall-inject slot.
*(Confidence MEDIUM — the exact regression is under-specified in the read-only evidence; this RFC
scopes it as a bounded diagnostic work-item: instrument the recall path, confirm which store is
skipped, then wire the both-store read. It is NOT a new store.)*

**Outage → spool → recovery → exactly-once replay (G-8).** basic-memory / event-ledger are OFF the
correctness path (Codex-RFC §3: "a deployment can plan, recover, compensate, and report when either is
unavailable"). But durable capture must survive an outage:

- **Spool:** when basic-memory is unreachable, capture writes append to a local spool file (bounded,
  rotating) instead of being lost.
- **Recovery + exactly-once replay:** on the next SessionStart with basic-memory reachable, drain the
  spool with an **idempotency key per note** (content-hash) so a replay after a crash mid-drain does
  not double-write. Test the full outage→spool→recovery→exactly-once path (G-8 explicit).

**`/self-reflect` (G-8: bounded post-milestone, typed output, NOT a Stop-hook).** Critically NOT a
Stop-hook — a Stop-triggered reflection is exactly the A1 `additionalContext`-on-Stop pattern that
loops. Instead:

- **Trigger:** the existing `/self-reflect` command (live) + the metaswarm pre-PR knowledge-capture
  gate ("after all work units pass final review but BEFORE the PR"). Invoked, not hooked.
- **Bounded + typed:** emit a typed schema (learnings / decisions / failures-with-falsifiable-preconditions
  / superseded-links), capped in size, written to basic-memory with supersession links (AGENTS.md §3/§8).
- **Rides:** the live `/self-reflect` skill + basic-memory `write_note`. **Replaces:** free-form Stop-hook
  reflection (the loop risk) and the un-typed capture that produces the no-supersession-marker debt.

**mem0 / vector-store stays NO-GO (G-8; AXIS-B §4; global memory verdict).** Re-confirmed dead-end —
reintroduces the rejected vector-store, ~97.8% junk. The doc-reconciliation registry (§1.3) is a
deterministic registry, explicitly NOT a knowledge DB.

---

## 4. ORCHESTRATION ENGINE H1–H8 + tiered helpers (G-6 — FULL, on native Workflow; H6 priority)

**Architecture (G-6, non-negotiable):** H1–H8 + the ~50 tiered items are **HELPERS/wrappers over the
native `agent()`/`parallel()`/`phase()` globals** (the saved-Workflow runtime documented by the
`workflow-authoring` skill). **NO 2nd runtime.** Each Hx is a library function the workflow author
calls; it does not replace or shadow the native scheduler.

**The 8 cross-lens gems (AXIS-B §1; source = the 48 KB `ULTRACODE-HARNESS-SOTA-DECISION-QUEUE`,
117 findings / 11 lenses):**

| Gem | What it adds | Rides / Replaces |
|---|---|---|
| **H1** | `budget.reserve()` sub-pools + graceful soft-exhaustion | rides native token accounting + PR-F cost ledger (§2); replaces unbounded fan-out spend |
| **H2** | HITL checkpoint / suspend-and-resume | rides the SDK context-editing / task-budgets; replaces "no human gate mid-run" |
| **H3** | typed `endReason` / **drop-receipt on every null** | rides the §5 typed-handoff schema; replaces silent null fan-in (a hung agent vanishes) |
| **H4** | `gather()` / settled `parallel()` | rides native `parallel()`; replaces the null-tolerant-barrier footgun (`filter(Boolean)` today) |
| **H5** | role-tiered model/effort routing defaults | rides the G-10 named profiles (§6) + the G-7 auto-router (§5); replaces hand-picking a model per agent |
| **H6 ★** | **per-agent timeout + stall heartbeat (barrier-deadlock escape)** | rides native `agent()`; **replaces the parallel() barrier with NO per-agent timeout → one hung agent deadlocks the phase** (the documented workflow-orchestration failure) |
| **H7** | `workflow_lint.py` stage-0 (SHADOW) | rides the plan-lint stage-0 the workflow-authoring skill already maps; replaces "author a broken workflow, find out at runtime" |
| **H8** | bounded `loop()` / `refineUntil()` | rides native loop primitives; replaces unbounded refine loops (ralph-loop lesson) |

**H6 is the PRIORITY (G-6, G-9 Wave-1).** It directly fixes the barrier-hang failure mode
(`feedback_workflow_orchestration`: "parallel() barrier has NO per-agent timeout → one hung agent
deadlocks the phase; detect by transcript write-freeze >25 min"). Concretely: each `agent()` call gets
a per-agent timeout + a stall-heartbeat (transcript-write-freeze detector); on timeout the agent is
dropped with a typed `endReason` (H3) and the barrier settles on the survivors (H4) rather than hanging
the cohort. This is the single highest-value orchestration fix and rides §2's stall-heartbeat telemetry.

**The ~50 tiered items (AXIS-B §1) — adopt as opt-in helpers:** execution-consensus `bestOfN`,
`panel()` de-biasing, seeded RNG (determinism), `mapReduce`, typed retry/`Result`, saga/race,
per-phase token attribution. Each is a helper; none is load-bearing for the core loop. Ship behind the
same OFF→SHADOW ladder where they touch enforcement (e.g. `workflow_lint` ships SHADOW).

**The 5 genuine owner decisions carried forward (AXIS-B §1, D1–D5) — these are NOT resolved here; they
are the orchestration residual for the owner:** D1 resume-cache model · D2 budget-exhaustion default
(hard-throw vs soft-sentinel) · D3 HITL depth (advisory vs safety-by-default irreversibility
interception) · D4 verification defaults vs opt-in · D5 patterns-library surface. *(These feed the ≤3
owner decisions; see §9.)*

- **Rides:** native `agent()`/`parallel()`/`phase()` + the `workflow-authoring` skill's plan-gate/
  design-gate Workflows + the SDK context-editing/task-budgets. **Replaces:** NO second orchestration
  runtime (explicit G-6 + Codex-RFC §13 non-goal) — the barrier-hang footgun and the null-fan-in
  footgun, not the scheduler.
- **Anti-overfit ledger (AXIS-B §1, 7 items):** carried forward whole so the Axis-B wave does not
  re-derive rejected designs.

---

## 5. MINGLING (G-7 — FULL mingle layer + vendor auto-routing; honor the threadId constraint)

**Through-line (Axis-C handoff):** ONE workflow system where any agent is Claude OR Codex (mingled),
scoped per-call, orchestrated by the §4 engine, monitored uniformly (§2), matching native `/workflows`.

**The primitives:**

- **`agent()`** = a Claude subagent (native).
- **`codexAgent()`** = a scoped-Codex thread via the mounted `codex mcp-server`
  (`mcp__codex__codex` / `mcp__codex__codex-reply`) — the **task-9 `codex-invoke`** primitive (HELD,
  complete but self-reviewed only: `tools/codex/profiles/`, `skills/codex-invoke/`,
  `guides/codex-invocation.md`, `modules.py` +56/−11 `~/.codex` edit-guard; `A5`/Axis-C handoff). Fold
  task-9 as the `codexAgent()` implementation.
- Both compose per-work-unit inside the same `parallel()` / `phase()` — a mixed-vendor agent team.

**The threadId constraint (HONORED — this shapes the design).** Each `codexAgent()` call is a FRESH
Codex process, **single-threaded + fresh-context (no cross-thread memory)** — the honest limit from
`~/.claude/CLAUDE.md`. Consequences the mingle layer must respect:

1. Cross-call continuity is ONLY via `threadId` (`codex-reply`) — so a multi-turn Codex work-unit must
   carry its `threadId` explicitly; there is no ambient Codex memory to lean on.
2. Structured typed handoffs are MANDATORY (AGENTS.md §5): never pass a Codex thread's raw output as
   the next agent's prefix — hand off a typed summary with the goal re-anchored (a Codex thread cannot
   "remember" the goal across a fresh spawn).
3. Telemetry keys by `threadId` (§2).

**Vendor auto-routing (G-7 — capability/cost/quota-aware).** A `route()` helper selects the vendor per
work-unit:

- **capability:** Codex is strong at execution / sandboxed run / independent reproduction; Claude leads
  architecture / planning / web research (`~/.claude/CLAUDE.md`). Route by the work-unit's shape.
- **cost/quota:** two independent subscriptions (Claude Max + ChatGPT) — spread load to maximize each
  WEEKLY quota, treat the 5 h window as a rate cap (the retired-AgentBridge budget principle, now by
  judgment). Feeds H1 budget sub-pools (§4).
- Rides the G-10 named profiles (§6) for the resolved model/effort per route.

**Architect-to-Editor split (orchestration-patterns skill; G-7).** An Opus **architect** (`agent()`)
emits a typed change-spec; a **Codex editor** (`codexAgent()`) applies it via the mounted rail —
cross-vendor diversity per work-unit. This is the flagship mingle pattern; it rides the existing
`orchestration-patterns` skill (already documents it for this Windows workspace).

**Cross-vendor execution-consensus (G-7).** Where an independent Claude candidate and an independent
Codex candidate AGREE on an executable outcome, that agreement is the signal (cross-vendor = independent
failure modes) — rides the `execution-grounded-bon` skill (JudgeBench: model-opinion rerank ≈ chance,
so use execution-consensus not an LLM judge). Ships SHADOW (observe + log, never blocks) per that skill's
contract.

**Live channel (Layer 2, advisory).** `mcp_agent_mail` (`:8812`) is the peer-chat + advisory
file-lease rail for interactive mid-task Codex questions. **NOTE the verified breakage:** `:8812` was
DOWN this session (supervisor task dead, `AUDIT-DESIGN-CONVERGED §1.3`) — the mingle layer must degrade
gracefully (the `multi-ai-mingle` skill has a fallback; a dead daemon must not block a workflow). Fan-out
(Layer 1, the `codexAgent()` rail) is the primary; the live channel is opportunistic.

- **Rides:** the mounted `codex mcp-server` (Layer 1) + `mcp_agent_mail` (Layer 2) + the
  `orchestration-patterns` / `execution-grounded-bon` / `multi-ai-mingle` skills + task-9 `codex-invoke`.
  **Replaces:** the RETIRED AgentBridge (Windows-broken) — this is its two-rail successor; NO new bridge
  daemon.

---

## 6. NEW FEATURES (G-10 profiles + G-11 features — adopt all, plus opportunistic)

**Named profiles (G-10).** Extend task-9's Codex profiles (`max`/`strict`/`balanced` overlays,
`A2 §5`) to Claude: named profiles (`audit-max` / `build-sandboxed` / `fast` / `fanout`) +
`effective-config explain` (rides the B1 SSOT engine's read-only `plan` op) + full precedence chain,
**per-session AND per-workflow-agent**, PLUS dynamic per-agent inline overrides. Feeds the §5 auto-router
(a route resolves to a profile) and §4 H5 role-tiered routing.

- **Rides:** task-9 Codex profiles + the B1 SSOT `Profile` type (Codex-RFC §5) + `effective-config
  explain`. **Replaces:** hand-tuning model/effort/tools per agent; the "which config is actually
  active?" opacity.

**G-11 features (all adopted; SHADOW-first where they touch behavior):**

| Feature | What | Rides / Replaces | Source |
|---|---|---|---|
| **Uncertainty-gated escalation** (confirm-don't-guess) | on a low-confidence load-bearing assumption, escalate/confirm instead of guessing | rides AGENTS.md §1b assumption-ledger + the EVPI gate; replaces silent worst-case bets | AXIS-B §3 (TG.8), OPEN-THREADS |
| **GEPA prompt-evolution** | self-improving workflow prompts (reflective prompt evolution) | rides `agent()` + H7 workflow_lint; replaces static hand-tuned prompts | AXIS-B §3 (TG.9) |
| **Proactive-partner router** | semantic capability router + EVPI intent-hook + `USER.md`-grows-with-you | rides the existing `semantic-router`/`skill-router` modules + `clarify-requirements` skill; replaces "I don't have that tool" mis-routes | AXIS-B §2, OPEN-THREADS, `feedback_uiux_figma_first` |
| **`/harness-audit` scorecard** as a recurring CI health-gate | a scorecard that grades the harness on a rubric, run in CI | rides the **live `/harness-audit` command** + `/self-reflect`; replaces ad-hoc "is the harness healthy?" | G-11; `/harness-audit` exists |

**Opportunistic surface (G-11 "+ more"; AXIS-B §3 reasoning-spine — STILL-OPEN, adopt as capacity
allows, NOT Wave-1):** Discipline-Forge (the "moat" capstone), TMS auto-retraction for RE,
Smith-predictor dead-time compensation, file-centric world-model ledger, hold-your-ground dissent,
backtracking executor, capability-gap tool-FORGE, sleep-time/idle compute (TG.11), Calibration-Brier
ledger (TG.1). These are catalogued so they are not lost; they are NOT in the operational Wave-1/2 scope.

- **Rides:** existing modules + skills + commands throughout. **Replaces:** nothing wholesale — these
  are additive capabilities, each ride-not-rebuild.

---

## 7. LEANNESS / ANTI-BLOAT BUDGETS (G-12 — every component states what it rides/replaces)

**Posture (G-12):** AGGRESSIVE on provably-dead + an RFC-enforced budget; EVIDENCE-FIRST on ambiguous
(`codacy`/`deepsource` STAY until owner decides); SALVAGE-FIRST for any unpushed work.

**The budget (RFC-enforced, measured against the current baseline — Codex-RFC acceptance gate #12):**

| Budget | Target | Enforced by |
|---|---|---|
| **Context/token** | net tool+token count per turn must NOT regress vs baseline; skills stay curated to the daily set (75, not the 283-vault) | the `context-budget` command + the daily-derived view (`S-RC4`) |
| **RAM** | no new always-on daemon; heavy MCPs (angr, RE, schrodinger) LAZY on-demand (re-ensure), NOT supervisor (G-5) | MCP lifecycle classes (Codex-RFC §7); `re-ensure` skill |
| **Latency/startup** | dispatcher stays ONE engine; the 63-residue + System B/C removal reduces the hook surface | §1.6 consolidation |
| **Hook-event ceiling** | ~6 active hook events; every new check folds into an EXISTING slot — NO new hook event | the design law (`B-doc §5`) |

**The prune backlog (all POST-GATE, from `C-config-reconciliation §3` — the cleanup hook's input, §1.2):**
provably-dead auto-propose (46 GB slop `S-SL*`; exact-dup skills `S-DD*`; superseded docs `S-SU*` with
valid supersession links; dormant hooks System B/C; stale MCP `M-ST*`). Evidence-first HOLD:
`codacy`/`deepsource` (`D6`) + ambiguous MCPs/skills. **Salvage-first prerequisite (MANDATORY, HIGH
risk):** the 22 daily-only "gem" skills (`S-BP`) exist ONLY in `~/.claude/skills.daily` with no source
— **back-port to `source/skills` BEFORE any daily regeneration**, or the 2026-07-12 gem-hunt adoptions
are lost.

**Anti-bloat guarantees (Codex-RFC §13 non-goals, adopted):** NO second orchestration runtime (§4), NO
second memory/vector/KG store (§3), NO observability SaaS (§2), NO new daemon/watcher, NO default eager
loading of every MCP or skill (§7). Each B2 component's "Rides / Replaces" line (§§1–6) is the leanness
receipt: every component rides existing infra and replaces a footgun, not adds a subsystem.

- **Component-by-component ride/replace ledger:** §1 rides the wired dispatcher + git pre-commit;
  §2 rides wfmon/monitorcore; §3 rides basic-memory + event-ledger + `/self-reflect`; §4 rides native
  `agent()`/`parallel()`; §5 rides `codex mcp-server` + task-9; §6 rides task-9 profiles + live commands.
  **Net new subsystems introduced: ZERO.**

---

## 8. RECOMMENDED WAVE-0 (leaving this gate — RELIABILITY first, G-9/G-13)

Per G-9 (RELIABILITY → SSOT → CAPABILITIES) and G-13 (ALL modifications POST-APPROVAL-GATE), the
recommended operational Wave-0 = **stop the bleeding, ride existing rails, lowest-risk-highest-value:**

1. **Stop-loop → CLOSED (§1.5):** hoist the re-entrancy guard to the dispatcher boundary (R2-2) +
   add correlation IDs + `StopFailure` branch + the T2/T4/T5/T7 tests. Land the enshrine chain on main
   (fold PR #78 → mainline, D0.2) + tie the receipt to a bundle digest. *(H6 §4 + this = the G-9 Wave-1
   reliability core.)*
2. **H6 per-agent-timeout + stall-heartbeat (§4):** the barrier-hang fix — highest-value orchestration
   change, rides native `agent()`.
3. **Enforcement hooks in SHADOW (§1.1–1.4):** ship the cleanup / doc-reconciliation / harness-change→doc+PR
   gates OFF→SHADOW (observe + log only). NO ADVISE/ENFORCE promotion until burn-in.
4. **Merge wfmon PR #76 (§2)** after review + wire the Codex-threadId telemetry adapter (observe-only).
5. **Decide the 3 plugin Stop hooks (§1.5)** — disable the unused 900 s codex gate; clear stale
   ralph-loop state files.

Everything else (full 11-PR monitoring, full H1–H8, mingle auto-router, new features, the prune
backlog) sequences into Waves 2–3 behind the SSOT engine (B1), per G-9/G-13.

---

## 9. OPEN ITEMS → the ≤3 owner decisions (operational residual)

The irreducible operational decisions this RFC surfaces (candidates for the program's ≤3 owner
decisions; the SSOT/deploy-mechanism decision is B1's):

1. **Orchestration D1–D5 (§4, AXIS-B §1) — the genuine engine defaults:** most load-bearing is **D2
   budget-exhaustion default (hard-throw vs soft-sentinel)** and **D3 HITL depth (advisory vs
   safety-by-default irreversibility interception)**. These change the engine's contract and cannot be
   inferred from evidence — owner call.
2. **The 3 plugin Stop hooks (§1.5, C-hooks §5 Q4):** disable the unused (esp. the codex 900 s gate),
   or keep all and rely on the dispatcher-boundary short-circuit? (Owner uses which?)
3. **ENFORCE-promotion trigger for the L1 hard pre-commit block (§1.1/§1.4):** what burn-in evidence
   promotes doc-reconciliation from SHADOW→ENFORCE (the first gate that can *fail a commit*)? STRONG-BUT-SAFE
   means the owner sets the bar for the teeth.

**Lower-stakes owner triage (not gate-blocking, C-hooks §5):** keep the 2 standalone-wired hook subdirs
+ 2 worktree `.ps1` separate or fold into the dispatcher; retire codex parity residue in lockstep with
the Claude residue.

---

## 10. EVIDENCE INDEX (load-bearing citations)

- **Stop-loop:** `A1-stoploop-incident.md` §0 (verdict ~90%), §3 (3 plugin Stop hooks), §6 (fix LIVE +
  before/after telemetry: 38 pre-fix runs → 0 post-fix), §10 (8 permanent-fix reqs), §11 (T1–T8).
- **Hooks consolidation:** `C-hooks-reconcile.md` §0 (three-way split, 63-residue → HIGH ~90% not-firing),
  §2 (disposition matrix), §3 (one-dispatcher plan), §5 (owner triage Qs).
- **Config reconciliation:** `C-config-reconciliation-COMPLETE.md` §1 (3 canonical declarations), §3
  (51-row prune backlog + `S-BP` 22-gem prereq), §4 (feeds G-1/G-3).
- **Doc / memory:** `B-doc-reconciliation-COMPLETE.md` §2 (two-memory role separation), §5 (doc-hook
  design A–F — adopted verbatim), §4 (forgotten-value + anti-re-walk guardrails).
- **Orchestration / Axis-B:** `AXIS-B-PRESERVE-INDEX.md` §1 (H1–H8 + D1–D5 + ~50 tiered), §3
  (reasoning-spine gems), §4 (dead-ends: mem0 NO-GO).
- **Monitoring / mingling:** `NEXT-WAVES-ROADMAP.md` Wave-2; Codex `HARNESS-CONTROL-PLANE-RFC-2026-07-13.md`
  §10 (monitoring observe-only), §13 (non-goals); basic-memory `harness-ssot-wave-0-shipped-axis-c-…`
  (task-9 codex-invoke, wfmon backbone, mingle through-line).
- **Provenance ground-truth:** `A5-decision-ledger.json` G1 (git chain `5d2fca2→…→dd5366b`), G2 (PR #78
  merged into stacked branch NOT main), G3 (enforcement now LIVE), `A2-inventory.md` §3 (R1 re-deploy),
  §5 (Codex profiles, both memory stores).
- **Grill decisions:** `GRILL-LOG.md` G-3/G-4/G-6/G-7/G-8/G-9/G-10/G-11/G-12/G-13 + R2-1/R2-2/R2-3.

*`SUCCESS:B2-RFC-operational` — READ-ONLY design; active-work freeze respected (no build / commit /
deploy / config-change / restart / delete). Every proposal is POST-APPROVAL-GATE (owner G-13). This
RFC gate ends here — it does NOT authorize implementation.*
