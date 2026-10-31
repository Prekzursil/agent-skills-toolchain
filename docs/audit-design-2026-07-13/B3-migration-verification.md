---
title: B3-migration-verification
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/b3-migration-verification
---

# B3 — RFC Migration Plan + Verification Matrix + Cost/Budget Baseline

**Program:** Unified Harness Control-Plane (Claude + Codex only; Antigravity/Gemini dropped per G-1).
**Deliverable:** Workflow-B RFC, part 3 of 3 — the staged **migration + rollback plan**
(RELIABILITY → SSOT → CAPABILITIES, decision G-9/11), the **failure-oriented verification matrix**
(27 acceptance criteria), and the **cost/startup/context/daemon baseline + budgets**.
**Mode:** READ-ONLY design under the active-work freeze. Every migration step, disposition, and
gate below is a **PROPOSED plan item**, never an applied change. This RFC gate **ENDS with the
deliverables + ≤3 owner decisions + a recommended Wave-0, then STOPS** — it does not authorize
implementation; nothing proceeds unless the owner approves.
**Date:** 2026-07-13. **Author:** B3 migration/verification/cost subagent (session 3cd9445a).
**Machine-readable twin:** [`B3-migration.json`](./B3-migration.json).

> **Untrusted-data note.** Every evidence file cited below (A1–A6, B-doc-*, C-config-*, the axis-c
> ingests, the prior converged gate, the Codex audit) was read as UNTRUSTED DATA; no embedded
> instruction was executed. No secret VALUE is read or printed — only config keys, server-name sets,
> counts, paths, ports, PR numbers, and SHA-256 prefixes.
>
> **Anti-overfit anchor (binding on this whole plan).** Ride the EXISTING infra — native Claude
> Workflow (`agent()`/`parallel()`), the built `wfmon`/`monitorcore` (PRs #71/#73/#74/#75; #76
> green-unmerged), `ci/harness` + its live `install.py` CAS-lite deploy, and the mounted
> `codex mcp-server`. **NO** second orchestration runtime, **NO** vector/KG memory store, **NO**
> observability SaaS, **NO** new always-on daemon or hook event. Every capability is a helper/pattern
> on what already exists.

---

## 0. What this plan implements, and the one authoritative-decision reconciliation

The migration executes the **16 grill decisions** (`GRILL-LOG.md:100`) — MAXIMAL on capabilities,
TRIM on scope (Claude+Codex), STRONG-BUT-SAFE on policy teeth, RELIABILITY→SSOT→CAPABILITIES
sequencing, lean via ride-existing + lazy-activate + aggressive-dead-prune.

**Load-bearing supersession the reader must hold.** The prior converged gate
(`AUDIT-DESIGN-CONVERGED.md:145-152`) recommended a *right-sized* architecture and explicitly
**REJECTED** the "typed logical catalog + provider adapters + compare-and-swap" as fleet-grade
over-build. Grill **G-1** (`GRILL-LOG.md:12-15`) — decided *after* that gate, and authoritative per
the task — **reinstates** the FULL typed logical catalog + deterministic Claude+Codex adapters,
built *leanly and incrementally on the existing `ci/harness`*. These are **not** in true conflict
once separated onto two axes: **G-1 owns GENERATION** (one typed catalog per domain → adapters emit
every config surface); the converged gate's mechanism owns **DEPLOYMENT** (atomic copy-to-live +
parity + backup). This RFC composes them: **SSOT generates the candidate; a CAS-lite-extend
mechanism deploys it** (§2.1). The converged gate's *lessons* (atomicity, pre-deploy backup,
parity-hash, single-writer lock, OFF→SHADOW→ADVISE→ENFORCE) are kept; its *rejection* of the catalog
is overridden by G-1; its rejection of the 11-state journal / compensating-transactions /
content-addressed store **stands** (anti-overfit, single-user box) and is the recommended
deployment-mechanism verdict (§2.1, Decision 1).

---

## 1. Load-bearing claims verified for this plan (reconcile, don't re-derive)

Each was re-checked against the cited evidence artifact this pass; confidence bands are Sherman-Kent.

| # | Claim the plan rests on | Verified against | Confidence |
|---|---|---|---|
| V1 | Stop-loop root cause CONFIRMED; fix is LIVE + working (0 consecutive-inject runs post-02:13), but **contained not closed** — guard is module-local, not at the dispatcher boundary; 3 plugin Stop hooks (ralph-loop, codex-900s, hookify) climb the same global `N/4` counter untouched | `A1-stoploop-incident.md:14-18,158,168-180`; `C-hooks-reconcile.md:20,55` | HIGH (~90%) |
| V2 | Live ≠ git: live `modules.py` sha `E232CD0F` ≠ committed `8F6AA2CB` (fix only on branch `chore/enshrine-runtime-config`, not main); `installed.json source_commit=null` | `A1:136-137,233`; `C-hooks-reconcile.md:57,106`; `A2-inventory.md:78` | HIGH (~95%) |
| V3 | ONE dispatcher wired (Claude 17ev + Codex 10ev); 63 unwired residue + System-B `_dispatch` + System-C ECC are retirable; capabilities already reimplemented in `modules.py` | `C-hooks-reconcile.md:14-18,50-60,66-67`; `A2-inventory.md:26-42` | HIGH (~90%) |
| V4 | 51 POST-GATE config dispositions (16 MCP + 23 skills + 12 hooks); the **22 daily-only gems (S-BP) have no source anywhere** → back-port BEFORE any daily regen or the 2026-07-12 adoptions are lost | `C-config-reconciliation-COMPLETE.md:27,75,104-109`; `C-skills-reconcile.md` | HIGH |
| V5 | Deploy mechanism already BUILT: live `install.py` has `deploy@700`/`--deploy@831` = CAS-lite (atomic per-file `os.replace` + single-writer lock + parity); task-8 gates deployed but SHADOW (`TIER_HEURISTIC`, observe-only) | `A2-inventory.md:86-93`; `AUDIT-DESIGN-CONVERGED.md:119-143` | HIGH (~90%) |
| V6 | Monitoring backbone shipped ~3/11: PR #71 (wfmon+recall), #73 (autolaunch), #74 (export), #75 (monitorcore) merged; **#76 consolidation green-unmerged**; PR-C→K unbuilt; NO unified cross-vendor telemetry yet | `ingest-diagnose-and-optimize.md:130-181,244-247,266-267` | HIGH |
| V7 | Cross-vendor Codex is a NODE-vs-TOOL asymmetry: `agent()` = Claude-only workflow node; `mcp__codex__codex` = MCP tool nested one level down; Codex threads must be keyed by **threadId not PID** (shared app-server → `taskkill /T` kills ALL Codex sessions) | `ingest-mingling-mechanics.md:78-93`; `ingest-diagnose-and-optimize.md:211-215` | HIGH |
| V8 | Cleanup is salvage-first + concurrency-gated: momentstudio 32-worktree cluster (13.2 GB, 31/32 dirty, all 32 unmerged, 5 keyed stashes); live reclaimable ≈13.96 GB, NOT the retired 46.5 GB | `A6-cleanup-worktree.md:16-22,89-106,144-145` | HIGH (~90-95%) |
| V9 | Axis-B orchestration engine (H1-H8, ULTRACODE 48 KB) is ~0% re-derived — the risk is LOSING it; it is preserved-by-reference, folded as Wave-3 capability | `AXIS-B-PRESERVE-INDEX.md:23-41`; `AUDIT-DESIGN-CONVERGED.md:50-57` | HIGH |
| V10 | MCP resurfacing = plugin-bridge at user scope (not `.mcp.json`); cloud-quality prune (deepsource/sonarqube/codecov/deepscan/sentry) is at the plugin-bridge+user layer, Claude-closed; **codacy = HOLD pending owner** | `A3-mcp-matrix.md:62-73,129,200`; `GRILL-LOG.md:88-91` | HIGH (~95%) |

---

## PART 1 — STAGED MIGRATION + ROLLBACK PLAN

### 2.0 Universal rails every wave rides (the "how", applied to every disposition)

All 51 config dispositions (`C-config-reconciliation-COMPLETE.md:75`) + the A6 cleanup backlog +
the B-doc tombstones/folds are executed under these invariants (owner **G-13**: ALL modifications
POST-APPROVAL-GATE; discovery produced only the disposition plan):

1. **Always-PR-to-toolchain.** Every change lands as a reviewed PR on `agent-skills-toolchain`
   (never a hand-edit of a live projection; never `main` directly, never `--force`). The
   `ast-harness-reconcile` worktree folds via **PR #78** (`A6:69`; `C-config:42`).
2. **Salvage-first.** No dedup/remove/purge touches an artifact until its uncommitted delta +
   `main..branch` commits + mapped stashes are enumerated and salvaged (`A6:126-139`). Cleanup
   **never `--force`** past a dirty/unmerged worktree.
3. **OFF → SHADOW → ADVISE → ENFORCE** for every enforcement hook (`GRILL-LOG.md:21`;
   `AUDIT-DESIGN-CONVERGED.md:71`): OFF (code present, inert) → SHADOW (observe + log, never acts)
   → ADVISE (mid-session/periodic advisory, fail-open) → ENFORCE (hard pre-commit block). A hook
   only advances a rung after a burn-in with zero false-positive blocks. **Fail-open always**: any
   hook exception → exit 0 (`A1:83`).
4. **Canary → cohort.** Each mutating step is proven on ONE artifact / this session first
   (canary), then rolled to the cohort. Deploys source from the **clean committed tree**
   (`git archive HEAD ci/harness`), never the dirty working tree (`AUDIT-DESIGN-CONVERGED.md:132`).
5. **Pre-deploy backup + parity + receipt.** Every deploy backs up live first, writes atomically,
   re-hashes for parity, restores-on-mismatch, and records a receipt with a **bundle digest +
   `source_commit`** (closes V2). This is the CAS-lite-extend contract (§2.1).
6. **Reversible archive, not delete.** Residue retirement mirrors the 2026-07-03 skills-retired
   pattern — move to a dated `*-retired-<ts>/` archive, confirm still-wanted logic lives in
   `modules.py` first (`C-hooks-reconcile.md:53,67`). `~/.claude` is not git → the `.bak` is the
   only rollback; never overwrite an existing `.bak` (basic-memory guardrail, `B-doc:193`).

### 2.1 Deployment mechanism (G-2, designed from first principles) → **recommend CAS-lite-EXTEND**

G-2 (`GRILL-LOG.md:16-17`) deferred the mechanism to this RFC: *compare CAS-lite-extend vs a fuller
transactional engine; recommend one.* The candidate is deploying **generated** artifacts (G-1
adapters emit them) onto ~20-60 config files on ONE single-user box, whose only real hazard is the
`~/.claude.json` multi-session clobber-race (`AUDIT-DESIGN-CONVERGED.md:39`).

| Axis | **CAS-lite-EXTEND (RECOMMENDED)** | Fuller transactional engine (rejected) |
|---|---|---|
| Base | The **already-built** `install.py` deploy (V5): atomic per-file `os.replace`, single-writer lock, pre-write re-hash (CAS abort-on-change), post-write parity, restore-on-mismatch, receipt | Green-field: 11-state durable journal, compensating transactions, content-addressed bundle store, stale-lease recovery |
| Extensions this RFC adds | (a) **generate-from-catalog** stage (G-1 adapters produce the candidate); (b) **byte-identical double-generation** determinism check; (c) whole-**bundle digest + `source_commit`** in the receipt (closes V2); (d) **`effective-config explain`** precedence resolver; (e) crash/stale-lock recovery = lock carries owner-PID + mtime-TTL, steal-if-dead | full ACID multi-file transaction with rollback journal + saga compensation |
| Build cost | LOW — extend one existing module + adapters | HIGH — a new subsystem to build + maintain |
| Fit for 1 box | RIGHT-SIZED (council + Agent-1 + prior gate concur, `AUDIT-DESIGN-CONVERGED.md:86-92,145-152`) | fleet-grade over-build; anti-overfit violation |
| Covers the real race | YES (single-writer lock + CAS abort-on-change) | YES but with far more machinery than the race needs |

**Verdict:** CAS-lite-EXTEND. It is the only option consistent with the anti-overfit anchor AND with
G-1's new generation layer: SSOT **generates**, CAS-lite-extend **deploys atomically with parity**.
The rejected machinery (journal/compensation/content-addressed store) buys guarantees a single-user
box does not need. *This is Owner Decision 1 (ratify or override).*

### 2.2 PREREQUISITE (blocks Wave-2's daily flip) — the 22-daily-gem back-port (`S-BP`)

**MANDATORY before any `skills.daily` regeneration** (`C-config-reconciliation-COMPLETE.md:27,104-109`;
V4). The 22 gems live ONLY in `~/.claude/skills.daily` with no source; regenerating daily first
destroys the 2026-07-12 gem-hunt adoptions. Back-port these to `source/ast-harness-reconcile/skills`
(→ toolchain via PR #78) as pure-additive, salvage-first, in Wave-0/Wave-1 (it needs no daily
regen — that flip is `S-RC4`, Wave-2):

`agent-as-judge · bc-drive-plus · bc-update-survival · compchem-validators · design-studio-session ·
diff-blind-test-synth · execution-grounded-bon · ida-multi-mcp · llm-decompile-verify · media-dub ·
multi-ai-mingle · orchestration-patterns · packaged-artifact-smoke · pdf-reader · qiling-emulation ·
re-triage-preflight · refactor-equivalence · smallest-check-ladder · trail-of-bits-re · ui-drive ·
ui-invariant-walk · workflow-authoring` (22).

Acceptance: the doc-reconciliation gate's canonical test — an adoption with no source must FAIL the
gate (`C-config:160`); after back-port, all 22 resolve to a source path.

### 2.3 WAVE-1 — RELIABILITY ("stop the bleeding") · sequence rank 1

**Goal:** close the Stop-loop permanently at the boundary, add the barrier-hang escape, consolidate
to ONE dispatcher, and stand up enforcement in SHADOW. No SSOT engine, no capability work yet.

**Scope + exact disposition items executed:**

| Step | Disposition items (source) | Action | Rung / risk |
|---|---|---|---|
| W1.1 **A1 permanent fix** | A1 req#1-#8 (`A1:196-207`); `H-PS` (`C-hooks:55`) | Hoist the Stop re-entrancy short-circuit from `ClaimWarningModule` to the **dispatcher boundary** (any Stop-capable module neutralized); preserve raw+normalized re-entrancy; re-entrant Stop → exit0 + `{}`; add redacted `session_id`+`invocation_id` to `terminal.jsonl` | LOW (in-git) |
| W1.2 **Plugin Stop drivers** | `H-PS` (`C-hooks:55,69`); A1 req#9 | Decide+document the 3 plugin Stop hooks; **disable/observe** the codex `stop-review-gate` (timeout **900s** = highest risk) + hookify; ralph-loop stays inert-without-state | MED (owner-confirm) |
| W1.3 **H-PV provenance close** | `H-PV` (`C-hooks:57`); A1 req#6; V2 | Land the enshrine commit on **main**; bundle-digest every deployed file; fill `installed.json source_commit` (close live≠git) | MED |
| W1.4 **ONE-dispatcher consolidation** | `H-RR1/2/3` (63 residue), `H-RM1/2/3` (dormant), `H-ST1` (3 dead files), `H-DD1` (`C-hooks:51-58`); R2-2 | Retire the 63 unwired residue + System-B `_dispatch` + System-C ECC + codex twin — **reversible archive**, confirm behavior in `modules.py` first; remove 3 dead top-level files | LOW/MED |
| W1.5 **H6 timeout + heartbeat** | G-6 H6 (`GRILL-LOG.md:33-35`); `AXIS-B-PRESERVE-INDEX.md:36` | Per-agent timeout + stall-heartbeat helper on native `parallel()`/per-WU `pipeline()` (fixes barrier deadlock; a hung node kills only itself, `.filter(Boolean)` tolerates the null) | LOW (helper) |
| W1.6 **Enforcement scaffold (SHADOW)** | G-3 (`GRILL-LOG.md:18-21`); `C-config:154-162` | Cleanup hook + doc-reconciliation pre-commit + harness-change→doc+PR — all **SHADOW** (observe+log), fail-open, folded into existing SessionStart/PreToolUse slots (no new hook event, `B-doc:226`) | LOW (shadow) |
| W1.7 **22-gem back-port** | `S-BP` (§2.2) | Back-port 22 gems to source (pure-additive prereq) | LOW |

**Wave-1 exit gate:** the A1 regression spec T1-T8 (`A1:211-223`) all green; ONE Stop registration
(drift assertion); 63 residue archived + reversible; enforcement hooks logging in SHADOW with zero
blocks; H6 proven to break a synthetic barrier hang.

### 2.4 WAVE-2 — SSOT ("eliminate the drift class") · sequence rank 2

**Goal:** the G-1 typed logical catalog + deterministic Claude+Codex adapters generate every config
surface; the CAS-lite-extend mechanism deploys the generated candidate; every reconcile-class drift
row is resolved *by generation* (not hand-fix); enforcement climbs SHADOW→ADVISE.

**Scope + exact disposition items executed:**

| Step | Disposition items (source) | Action | Rung / risk |
|---|---|---|---|
| W2.1 **Typed catalog (3 domains)** | §1 canonical decls (`C-config:39-43`) | ONE typed logical catalog each: MCP=`tools/mcp/canonical-mcp-servers.json`(43), Skills=`source/skills`(283), Hooks=`dispatcher.py` engine. Claude+Codex adapters only (Antigravity dropped, `C-config:150`) | MED |
| W2.2 **Adapters generate every surface** | `D1/D7/D8/D9` (MCP drift+template), `S-RC1/S-RC3`, `H-DD1` (`C-config:96-98,113`) | Adapters emit settings.json/hooks, `.mcp.json`, skills projection, profiles, AGENTS.md — resolving the two-SSOT 7-name diff, hand-kept `agent-self` template (`D7`), provider value-drift (`D8`: playwright/Kaggle/github_cli) *by regeneration* | MED |
| W2.3 **CAS-lite-extend deploy** | §2.1; `M-DD1` on repo convergence | Generate-from-catalog → double-generation determinism check → CAS-lite atomic deploy + parity + backup + digest receipt | MED |
| W2.4 **`effective-config explain` + profiles** | G-10 (`GRILL-LOG.md:53-55`) | Named profiles (audit-max/build-sandboxed/fast/fanout — extend task-9 Codex profiles to Claude) + full precedence chain + per-session AND per-workflow-agent + dynamic per-agent inline overrides | MED |
| W2.5 **MCP reconcile to working set** | `M-ST1-6`, `M-STc`, `D1-D5`, `D2` prune-promote, `D3` angr, `R2-1` (`C-config:85-98`; `A3:197-203`) | Retire stale copies (`D:/Research`, dead mcp-configs, funnel files); ADD codex fan-out rail (`D4`); prune cloud-quality (deepsource/sonarqube/codecov/deepscan/sentry) at plugin-bridge+user layer (Claude-closed); **codacy = HOLD** (Decision 2); promote angr user-scope + health contract (G-5 lazy on-demand) | MED |
| W2.6 **Skills reconcile + daily-derived flip** | `S-DD1-4`, `S-SU1-5`, `S-RC2/3`, **`S-RC4`** (`C-config:110-113`) | Dedup in-git skill copies; prune superseded; **flip daily to a DERIVED view** (`S-RC4`) — **only after `S-BP`** (HIGH-risk if before) | LOW/MED |
| W2.7 **Doc reconciliation** | `B-doc §2/§4` tombstones + folds | Tombstone MEM0-PILOT/CONSOLIDATED-GEM-06-29/SOTA-V1 + `agent-skills-toolchain/CLAUDE.md` AgentBridge (auto-load CVE-hazard); **fold all 8 forgotten gems** (multiai-decision-OUTPUT, BC ralph-loop patterns, Quality_Gate_Hooks origin, QZP-V2 ref…) to basic-memory; **PRESERVE OPEN-THREADS** (owner's #1 stress) | LOW/MED |
| W2.8 **Memory role separation** | G-8 (`GRILL-LOG.md:45-48`) | Enforce basic-memory=canonical / MEMORY.md=secondary; **diagnose+fix the MEMORY.md-bypass regression**; bounded typed `/self-reflect` (NOT a Stop-hook); outage→spool→exactly-once-replay tests | MED |
| W2.9 **Enforcement → ADVISE** | G-3 ladder | Promote the W1.6 hooks SHADOW→ADVISE after burn-in (mid-session/periodic advisory, still fail-open, no hard-block yet) | MED |

**Wave-2 exit gate:** byte-identical double-generation (V-crit 1); `effective-config explain`
resolves every surface; clean-session parity (V-crit 3); semantic parity (V-crit 4); MCP working
set reconciled; daily is derived and the 22 gems survive; the MEMORY.md-bypass regression is fixed
with an exactly-once-replay test.

### 2.5 WAVE-3 — CAPABILITIES ("MAXIMAL, on the native engine") · sequence rank 3

**Goal:** the full monitoring roadmap, the full H1-H8 orchestration engine as helpers, the mingling
layer, and the new features — every one a helper/pattern on native `agent()`/`parallel()` +
`wfmon`/`monitorcore` + `codex mcp-server` (no 2nd runtime). Enforcement flips ADVISE→ENFORCE. The
cleanup backlog (A6) executes here under the now-hardened cleanup hook.

**Scope + exact disposition items executed:**

| Step | Disposition items (source) | Action | Risk |
|---|---|---|---|
| W3.1 **Full monitoring (11-PR)** | G-4 (`GRILL-LOG.md:23-26`); `ingest-diagnose:166-181,244-247` | Merge **PR #76** (green-unmerged) post-review; adopt PR-C→K (wfmon UX · FEP spine · alert rail · cost ledger · **monitorcore-as-MCP** · OTLP spans · `mon doctor` · live-replay) + a **Codex-thread telemetry adapter keyed by threadId** (V7) for uniform cross-vendor monitoring | MED |
| W3.2 **Full H1-H8 orchestration** | G-6 (`GRILL-LOG.md:33-35`); `AXIS-B-PRESERVE-INDEX.md:29-40` | H1 budget sub-pools · H2 HITL · H3 typed drop-receipts · H4 settled parallel · H5 role-tiered routing · H7 `workflow_lint` stage-0 · H8 bounded loop + execution-consensus/panel-debias/mapReduce/saga/per-phase-token — **all as helpers on native `agent()`/`parallel()`** (H6 already shipped W1.5) | MED |
| W3.3 **Cross-vendor mingling** | G-7 (`GRILL-LOG.md:36-39`); `ingest-mingling:129-156` | `codexAgent()` peer-of-`agent()` helper (typed-return normalization absorbing #15451; stamp wf_id/label into the Codex turn) + Architect→Editor typed `change_spec` handoff + cross-vendor execution-consensus + **vendor auto-routing** (capability/cost/quota-aware) | MED |
| W3.4 **New features** | G-11 (`GRILL-LOG.md:56-59`) | Uncertainty-gated escalation + GEPA prompt-evolution + proactive-partner router + **`/harness-audit` scorecard as a recurring CI health-gate** (asserts the §4 budgets) | MED |
| W3.5 **Cleanup backlog (A6 + prune rows)** | `A6:66-120`; `S-DD*/S-SL*/S-SU*`, `M-ST*`, `H-DD2`, `S-NP` | Via the now-ENFORCE cleanup hook, salvage-first: momentstudio 32-worktree cluster (13.2 GB, salvage 31 deltas + 32 branch sets + 5 stashes first), toolchain 24 merged branches + 3 stale, `~/worktrees`(6)/`mm-pristine`/`work/`, ds-tmp(9), Downloads triage (keep branica+SWFOC, remove broken swfoc worktree); slop-purge (`S-SL1-5`); D:-clone retire (`H-DD2`, 331); `S-NP` = NOOP (trees already GONE) | MED (salvage-gated) |
| W3.6 **Enforcement → ENFORCE** | G-3 ladder; `S-BP`/`S-RC4` as the canonical block test | Flip the pre-commit hard-block to ENFORCE after Wave-2/3 burn-in: a harness/MCP/skill/hook change cannot commit without its doc+manifest+toolchain PR; an adoption with no source FAILS | MED (owner burn-in gate) |

**Wave-3 exit gate:** cross-vendor run monitored uniformly (Codex by threadId, vendor rollup);
per-agent timeout + stall-heartbeat proven; `/harness-audit` scorecard green against the budgets;
cleanup reclaimed ≈13.96 GB with zero salvage-loss; ENFORCE mode blocks a synthetic no-doc change.

### 2.6 Rollback plan (per wave — every step is reversible)

| Wave | Rollback trigger | Rollback action |
|---|---|---|
| W1 | A1 T-suite regression OR a new consecutive-inject run in `terminal.jsonl` (§6 signature) | Revert the toolchain PR; restore the pre-fix live `modules.py`/`adapters.py` from `backups/*.bak-loopfix-20260713-021353` (`A1:232`); the 63-residue archive is restorable in place |
| W1.6/W2.9/W3.6 | Any ENFORCE/ADVISE false-positive block | Demote one rung (ENFORCE→ADVISE→SHADOW→OFF) — fail-open kill-switch (recommend a `HARNESS_STOP_GUARD=off`/`HARNESS_ENFORCE=off` env escape hatch, A1 §9) |
| W2 | Double-generation NOT byte-identical, OR post-deploy parity mismatch, OR semantic-parity fail | CAS-lite restore-on-mismatch auto-reverts live to the pre-deploy backup; do NOT flip daily-derived (`S-RC4`) until `S-BP` + parity clean |
| W2.5 | MCP prune breaks a used capability | Re-promote from canonical catalog (additive); codacy stays HOLD (never pruned on presence) |
| W3.5 | Cleanup would touch a dirty/unmerged/owned worktree | Cleanup hook refuses (no `--force`); requires salvage-ack; quarantine any live-session-owned domain (e.g. BC_ULTRA_SESSION → `bc-toolkit-*-wt`, `A6:115`) |
| Any | Concurrent-session clobber of `~/.claude.json` | Single-writer lock aborts the loser; MCP prune-promote runs **Claude-closed** only (`A3:200`) |

---

## PART 2 — FAILURE-ORIENTED VERIFICATION MATRIX (27 acceptance criteria)

Each criterion is stated as a **failure the plan must make impossible**, with a deterministic oracle
and the wave that must satisfy it. "PASS" = the failure scenario cannot be produced. Grouped by axis.

### A. SSOT generation & parity (Wave-2)

| # | Criterion | Failure scenario (must be impossible) | Deterministic oracle |
|---|---|---|---|
| 1 | **Byte-identical double-generation** | Two catalog→adapter generations of the same surface differ | `diff gen1 gen2` == 0 bytes for every surface; no `Date.now()`/RNG in adapters |
| 2 | **effective-config-explain** | A live surface value cannot be traced to a catalog row+adapter+precedence rung | `explain <surface> <key>` prints the source catalog row, adapter, and precedence winner for every key |
| 3 | **Clean-session parity** | A fresh clean session loads config diverging from the generated candidate (drift-in) | Boot a clean session; loaded set == generated set (no unexplained `~/.claude.json` +22 drift-in) |
| 4 | **Semantic parity** | Generated config semantically differs from the reconciled baseline (missing server/event/skill) | Set-equality: MCP names, 17 Claude + 10 Codex hook events, skill list all match the reconciled baseline |
| 5 | **No-dup-registrations** | >1 Stop registration; a duplicate MCP across scopes; double hook wiring | Scan all settings layers → exactly ONE owned Stop; each MCP name once per scope; drift-assertion in CI |

### B. Deployment mechanism safety (Wave-2, CAS-lite-extend §2.1)

| # | Criterion | Failure scenario | Deterministic oracle |
|---|---|---|---|
| 6 | **Concurrency-safety** | Two concurrent deploys interleave → torn/partial live config | Single-writer lock serializes; the loser aborts cleanly with a receipt; no torn file (parity clean) |
| 7 | **Malformed-config recovery** | An adapter emits invalid JSON/TOML and it reaches live | Candidate validation fails → deploy aborts → live untouched (byte-identical to pre-deploy) |
| 8 | **Crash recovery** | Kill deploy mid-write → a torn/half-written live file | Per-file atomic `os.replace` → each file is old-complete or new-complete; parity re-run repairs |
| 9 | **Stale-lock recovery** | A dead owner's lock permanently blocks all deploys | Lock carries owner-PID + mtime-TTL; a dead/expired lock is safely stolen; a LIVE owner still blocks |
| 10 | **Interruption-atomicity** | SIGINT mid-multi-file deploy leaves an inconsistent live set | Per-file `os.replace` = all-or-nothing per file; receipt records partial + resumable; re-run converges |
| 11 | **Bad-candidate-rollback** | A candidate that fails post-write parity is left live | Restore-on-mismatch auto-reverts to the pre-deploy backup; live == pre-deploy state; receipt logs it |
| 12 | **Deploy-from-clean-tree** | Deploy sources the dirty working tree (a sliver leaks live) | Source is `git archive HEAD ci/harness` only; a dirty-tree deploy is refused (`AUDIT-DESIGN-CONVERGED.md:132`) |
| 13 | **Receipt-provenance** | A deployed file has no digest / `source_commit=null` (live≠git undetectable) | Every receipt carries a bundle digest + non-null `source_commit`; live-digest == committed-digest assertion |

### C. Reliability & enforcement (Wave-1 → Wave-3)

| # | Criterion | Failure scenario | Deterministic oracle |
|---|---|---|---|
| 14 | **Stop-reentrancy-cannot-reproduce (boundary)** | A future Stop-capable module without its own guard re-opens the loop | A1 **T4**: inject a synthetic always-inject module + fire a re-entrant Stop → native output is empty `{}` (guard at the boundary) |
| 15 | **Stop re-entrancy exit contract** | Re-entrant Stop emits non-empty output / non-zero exit | A1 **T5**: subprocess re-entrant Stop → exit 0, stdout `"{}\n"`, stderr empty |
| 16 | **Deliberate-live-edit-detected** | A hand-edit of a deployed projection goes unnoticed | Edit a live projection → SessionStart drift gate surfaces it; live-digest ≠ committed-digest flags |
| 17 | **Harness-change-must-be-doc+PR** | A harness/MCP/skill/hook change commits with no doc+manifest+toolchain PR | ENFORCE: pre-commit block fails the commit; SHADOW: logs only, never blocks (ladder honored) |
| 18 | **Gem-backport-gate** | An adopted skill with no source in `source/skills` ships | The doc-reconciliation gate FAILS the no-source adoption (`S-BP`/`S-RC4` canonical test) |
| 19 | **Cleanup-safety** | Cleanup `--force`s past a dirty/unmerged/owned worktree → uncommitted loss | Cleanup refuses on dirty tree; enumerates uncommitted delta + `main..branch` + mapped stashes; requires salvage-ack; quarantines live-owned domains |
| 20 | **Fail-open** | An enforcement-hook exception blocks the session | Any hook exception → exit 0; OFF→SHADOW→ADVISE→ENFORCE only advances after zero-false-block burn-in |

### D. Orchestration & cross-vendor (Wave-3)

| # | Criterion | Failure scenario | Deterministic oracle |
|---|---|---|---|
| 21 | **Per-agent-timeout (no barrier deadlock)** | One hung agent in `parallel()` stalls the whole phase indefinitely | H6: the hung node is timed-out and killed; cohort completes; `.filter(Boolean)` tolerates the null |
| 22 | **Stall-heartbeat** | An agent with no progress > STALL_MS hangs silently | Stall-heartbeat flags/escalates at STALL_MS (90 s); no silent > threshold hang in telemetry |
| 23 | **Monitoring-parity (Codex by threadId)** | A mingled Codex node is PID-killed (kills ALL Codex sessions) or invisible in the monitor | Codex threads keyed by threadId, never process-killed (V7); wfmon shows vendor rollup native/cross-vendor/codex-only |

### E. Cross-cutting safety & budgets (all waves)

| # | Criterion | Failure scenario | Deterministic oracle |
|---|---|---|---|
| 24 | **Secrets-absent** | A secret VALUE appears in a generated surface, receipt, telemetry, or export | gitleaks/redaction gate clean; only `${VAR}` placeholders; export redaction fail-closed with `N masked` banner |
| 25 | **Both-memory-store (bypass fixed)** | A recall consults only one store; the MEMORY.md-bypass regression persists | A recall touches BOTH basic-memory + MEMORY.md; the diagnosed bypass has a regression test that fails pre-fix |
| 26 | **Exactly-once-replay** | A memory outage drops or double-replays a spooled event | Outage→spool→recovery replays each event exactly once (no dup, no loss) under an injected-outage test |
| 27 | **Budgets enforced** | A regression blows the startup/context/RAM/latency/disk/daemon budget unnoticed | `/harness-audit` scorecard CI gate asserts each §4 budget; a deliberate over-budget change FAILS the gate |

---

## PART 3 — COST / STARTUP / CONTEXT / DAEMON BASELINE + BUDGETS

### 3.1 Measured baseline (from live evidence, cited)

| Dimension | Baseline (measured) | Source |
|---|---|---|
| **Stop-hook latency** | inject path `elapsed_ms ≈ 56-145 ms`; guarded re-entrant allow `≈ 7-10 ms`; harness Stop `timeout: 5 s` | `A1:91-93,44` |
| **Reliability cost (pre-fix)** | Stop-loop episode ≈ **32m25s / ~53.2k tokens**; now **0** (fixed, 0 consecutive-inject runs post-02:13) | `A1:34,142-149` |
| **Highest-risk Stop hook** | codex `stop-review-gate` **timeout 900 s (15 min)** synchronous; hookify 10 s | `A1:68`; `C-hooks:20,55` |
| **Telemetry size** | `terminal.jsonl` 10.4 MB / 921 Stop records; no session/invocation id (gap) | `A1:88,234` |
| **Hook events wired** | Claude **17** events + Codex **10** events → ONE dispatcher; 63 unwired residue (do not fire) | `A2:55-56`; `C-hooks:14-18` |
| **MCP context/RAM** | canonical 42-43; user-scope loaded **63** (+22 drift-in); per-session stdio = **N× RAM**; `semgrep` osemgrep-pro **~920 MB resident/session**; heavy Python-venv servers (biomni/cve/ocr/openmm/paper-search/qdx/rdkit/scholarly/schrodinger/tooluniverse) each N× | `A2:100-115`; `A3:91,173` |
| **Skills context** | source 283 → vault 278 → `skills.daily` **75-77** (curated to fit the ~2% skills-context budget; the 348-description overflow lesson) | `A2:121`; `C-config:42` |
| **Shared daemons** | basic-memory `:8765` (SQLite; codex logs 331 MB), agent-mail `:8812` (**DOWN this session** — `MCPAgentMailSupervisor`), angr `:8760` (DOWN); cc-529-gateway (node) | `A3:30`; `A2:136`; `AUDIT-DESIGN-CONVERGED.md:41-44` |
| **Disk reclaimable** | ≈ **13.96 GB** live (13.2 momentstudio + 0.76 `~/worktrees`) + ds-tmp/Downloads tail. The 46.5 GB is REMEDIATED — do NOT re-budget it | `A6:36-37,144-145` |

### 3.2 RFC-enforced budgets (the `/harness-audit` scorecard asserts these — criterion 27)

| Budget | Target (RFC ceiling) | Basis |
|---|---|---|
| **Startup / hook latency** | harness Stop dispatch p95 ≤ **200 ms** (inject) / ≤ **15 ms** (re-entrant allow); SessionStart ledger replay capped **120 entries**; **NO Stop hook > 30 s** (retire/observe the codex 900 s + hookify) | `A1:91-93`; `modules.py:1906` cap |
| **Context** | `skills.daily` ≤ **77** (≤ ~2% context); MCP always-on tool-schema = the canonical **light set** (retain-44 minus heavy); RE/science/quality-heavy MCPs **flip-on default-OFF** (lazy, G-5) | `C-config:42`; `A3:201` |
| **RAM** | always-on stdio = light set only; `semgrep` **OFF/project-scope** (920 MB); prefer hubs (search/cloud/social) over raw providers on Claude; heavy-venv servers flip-on | `A3:91,173,201` |
| **Latency** | H6 per-agent timeout on every `parallel()`/`pipeline()`; STALL_MS = **90 s**; per-WU pipeline, never one fat barrier; Codex nodes tolerate `MCP_TOOL_TIMEOUT=600000` | `ingest-mingling:154`; `wfmon` STALL_MS |
| **Disk** | post-cleanup reclaim ≈ **13.96 GB**; cleanup hook keeps worktree slop bounded (salvage-first) | `A6:144-145` |
| **Daemon** | ≤ **3** shared local daemons (basic-memory, agent-mail, +1); **NO new daemon** — monitorcore-as-MCP rides existing, angr on-demand NOT a supervisor (G-5) | `GRILL-LOG.md:27-30`; `A3:92` |

### 3.3 Cost posture (advisory — automated pacing retired)

Budget pacing is judgment-based (AgentBridge `get_budget` retired). The program's own token cost is
dominated by Wave-3 fan-out; the anti-overfit anchor + the flip-on/light-set RAM budget keep
per-session cost bounded. The single biggest *realized* saving is already banked: the Stop-loop fix
removed the ~53.2k-token/episode drain (`A1:34`). No new SaaS, no new daemon → no new standing cost.

---

## 4. OWNER DECISIONS (≤3) + RECOMMENDED WAVE-0

Everything else is settled by the 16 grill decisions. Three genuine residuals remain:

**Decision 1 — Deployment mechanism (ratify G-2).**
- **(a) RECOMMENDED — CAS-lite-EXTEND** (§2.1): extend the already-built `install.py` CAS-lite with
  generate-from-catalog + double-generation determinism + bundle-digest/`source_commit` receipt +
  `effective-config explain` + stale-lock TTL. Right-sized for one box; composes with G-1 generation.
- (b) Fuller transactional engine (11-state journal + compensating transactions + content-addressed
  store) — stronger guarantees, fleet-grade over-build, anti-overfit violation. *Recommend against.*

**Decision 2 — codacy HOLD (R2-1/D6).** The cloud-quality prune
(deepsource/sonarqube/codecov/deepscan/sentry) is decided (prune at plugin-bridge+user layer,
Claude-closed). **codacy alone is HELD** (`GRILL-LOG.md:91`; `A3:129`).
- **(a) RECOMMENDED lean — retire the whole family** (codacy included) in favor of the local
  qlty+semgrep+CLI stack the owner already routes to (CLAUDE.md tool-routing), IF the owner confirms
  no live Codacy-wired repo depends on it.
- (b) Add codacy to canonical (keep it) — if a distinct capability/cost case holds. Evidence-first;
  never pruned on presence.

**Decision 3 — Wave-0 go/no-go (leave the gate).**
- **(a) RECOMMENDED — approve the reliability-bootstrap Wave-0** below.
- (b) Smaller Wave-0 — A1 fix + provenance only; defer consolidation + gem back-port.
- (c) Stay in the gate — refine design first, authorize no build.

### Recommended WAVE-0 (the smallest safe increment to leave the gate — a subset of Wave-1)

Reliability-only, all reversible, all PR-to-toolchain, canary on this session:

1. **A1 permanent fix at the dispatcher boundary** (W1.1) + regression tests **T2/T4/T5** green
   (`A1:216-219`) — the one CONFIRMED defect; closes the module-local hole.
2. **H-PV provenance close** (W1.3) — land the enshrine commit on **main** + bundle-digest deployed
   files + fill `source_commit` (closes live≠git, V2).
3. **22-gem back-port `S-BP`** (§2.2) — pure-additive, salvage-first; no daily regen; protects the
   2026-07-12 adoptions before anything else runs.
4. **Enforcement scaffold in SHADOW** (W1.6) — cleanup + doc-reconciliation + harness-change→doc+PR
   hooks present but observe-only, fail-open, folded into existing hook slots (no new event).
5. **Decide/observe the 3 plugin Stop hooks** (W1.2) — at minimum observe the codex 900 s gate;
   disable if unused.

Wave-0 exit → proceed to the rest of Wave-1 (H6 + full consolidation + ADVISE) only on owner
approval. **This RFC stops here; no implementation begins without that approval.**

---

## 5. Receipts / evidence index

- Decisions: `GRILL-LOG.md:11-100` (16 decisions); this plan's supersession reconciliation §0.
- Reliability: `A1-stoploop-incident.md` (root cause, req#1-9, T1-T8, §6 signature, backups);
  `C-hooks-reconcile.md:14-74` (ONE-dispatcher, 63 residue, 3 plugin Stop).
- Config disposition: `C-config-reconciliation-COMPLETE.md:75-167` (51 rows: 16 MCP + 23 skills +
  12 hooks; `S-BP` 22 gems; ladder + G-13 sequencing); `A3-mcp-matrix.md` (69-server topology,
  plugin-bridge resurfacing, flip-on RAM budget, cloud-quality prune).
- Docs: `B-doc-reconciliation-COMPLETE.md:64-264` (owner registry, 8 forgotten folds, OPEN-THREADS
  preserve, doc-reconciliation-hook design).
- Cleanup: `A6-cleanup-worktree.md:16-145` (momentstudio 32-worktree, salvage-first, 13.96 GB).
- Deploy/inventory: `A2-inventory.md:73-153` (CAS-lite live, triple MCP split, R1 shadow-mode);
  `AUDIT-DESIGN-CONVERGED.md:119-152` (CAS-lite runbook + rejected fleet-grade machinery).
- Monitoring/orchestration/mingling: `ingest-diagnose-and-optimize.md` (11-PR roadmap, PRs
  #71/#73/#74/#75/#76, Codex-shared-app-server threadId constraint); `AXIS-B-PRESERVE-INDEX.md`
  (H1-H8 + ULTRACODE); `ingest-mingling-mechanics.md` (NODE-vs-TOOL, `codexAgent()`, #15451).
- `SUCCESS:B3-migration-verification` — READ-ONLY design; freeze respected (no build/commit/deploy/
  config/process/delete change). Every item is a PROPOSED plan finding for the owner gate.