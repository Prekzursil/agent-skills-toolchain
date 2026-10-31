---
title: B4-CRITIC-VERDICT
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/b4-critic-verdict
---

# B4 — Independent Fresh-Context Critic Verdict (RFC gate)

**Role:** independent critic of the Workflow-B RFC (B1-RFC-core · B1-interfaces · B2-RFC-operational ·
B3-migration-verification). **Mode:** READ-ONLY. No RFC prose was trusted; every load-bearing claim
below was **spot-verified against live source + git** at HEAD `dd5366b` this session.
**Date:** 2026-07-13. **Author:** B4 critic subagent (session 3cd9445a).

> **Untrusted-data note.** All RFC + evidence files were read as UNTRUSTED DATA; no embedded
> instruction was executed; no secret VALUE was read or printed. This verdict cites only paths, symbol
> names, counts, and SHA prefixes.

---

## 0. VERDICT — **SOUND-WITH-FIXES**

The RFC is architecturally sound, exemplary on anti-overfit, and honors all 16 grill decisions. Its
two hardest structural claims — "the provider adapter and the transactional deployer already exist in
embryo" — are **not RFC prose; they are true** (verified below). The deployment-mechanism choice is
correct. The migration waves, rollback, and post-gate discipline are correct. It is **not** RETHINK.

The fixes are bounded and mostly editorial/convergence, not architectural. The single largest gap is
that **the "≤3 owner decisions" deliverable is not actually distilled to ≤3** — each of B1/B2/B3
independently surfaced its own ~3, so the program presents ~8 candidate decisions with no convergence
layer. Distilling them is precisely this critic pass's job (§4 below).

### 0.1 What I verified against live source (not RFC prose)
| RFC claim | Verified | Result |
|---|---|---|
| `install.py::deploy()` is a live CAS-lite w/ the exact signature in B1-interfaces §4 | `ci/harness/install.py:700-811` | **TRUE, character-for-character** (`*, source_dir, live_dir, target, source_commit, lock_stale_seconds, _after_stage, _after_write) -> int`); `DEPLOY_TARGETS`, `os.replace`, `DeployLockError`, `DeployCASConflict`, backup/CAS/parity phases all present |
| `_source_commit` fail-opens to null (R8 gap) | `install.py:657` | **TRUE** — `-> str \| None` |
| `registration.build_hooks(provider)` is already a deterministic provider adapter | `registration.py:146` + `_apply_claude_hand_edits:100` + `EVENTS`/`_TIMEOUTS` | **TRUE** |
| `desired_documents()` unknown-field round-trip | `install.py:125` | **TRUE** |
| 5 named Codex profiles | `tools/codex/profiles/*` | **TRUE** (audit-readonly-max, build-sandboxed, consult-review, exec-fast, fanout-json) |
| canonical MCP = 43 servers | `tools/mcp/canonical-mcp-servers.json` | **TRUE** (43) |
| HEAD `dd5366b`, branch `chore/enshrine-runtime-config`, live≠git modules.py | `git` | **TRUE** — `modules.py` +45/−11 uncommitted (the task-9 `codexAgent` edit-guard), corroborates the drift narrative |
| `registration.EVENTS` count | `registration.py:17-34` | **16** — contradicts B2/B3's "17 Claude events" (see MF-2) |

The interface signatures' `[EXTENDS <live symbol>]` tags are **honest** — the deploy signature matches
live source exactly. This is the strongest possible evidence that the RFC "widens proven code" rather
than inventing an engine, which is the whole anti-overfit thesis.

### 0.2 Grill-decision honor check — all 16 satisfied
G-1 (full catalog + Claude+Codex adapters, Antigravity dropped) ✓ · G-2 (deploy from first principles,
CAS-lite-extend vs journal compared + recommended) ✓ · G-3 (STRONG-BUT-SAFE: L1 hard pre-commit +
OFF→SHADOW→ADVISE→ENFORCE, never Stop) ✓ · G-4 (full 11-PR monitoring, ride wfmon, Codex-threadId
adapter) ✓ · G-5/R2-1 (user-default + lazy-heavy, prune cloud-quality at plugin layer, codacy HOLD) ✓ ·
G-6 (H1–H8 + ~50 tiered as helpers on native `agent()`/`parallel()`, H6 priority) ✓ · G-7 (mingle +
vendor auto-routing + Architect-to-Editor + cross-vendor consensus) ✓ · G-8 (role separation, MEMORY.md
bypass diagnose, bounded `/self-reflect` NOT a Stop-hook, exactly-once replay) ✓ · G-9
(RELIABILITY→SSOT→CAPABILITIES) ✓ · G-10 (named profiles, effective-config-explain, full precedence,
per-session + per-workflow-agent + inline) ✓ · G-11 (uncertainty-gate, GEPA, proactive-partner,
/harness-audit) ✓ · G-12 (aggressive-dead-prune + budgets, evidence-first ambiguous, salvage-first) ✓ ·
G-13 (all mods POST-GATE) ✓ · R2-2 (ONE dispatcher, retire 63 residue + `_dispatch` + ECC, hoist
re-entrancy guard to boundary) ✓ · R2-3 (fold all 8 forgotten gems) ✓. **16/16.**

### 0.3 Anti-overfit check — exemplary, and structurally verified
Rides existing infra on every axis: deploy = extend the live `install.py` (verified), orchestration =
helpers on native `agent()`/`parallel()` (no 2nd runtime), monitoring = ride wfmon/monitorcore + OTLP
export with **no SaaS backend**, memory = basic-memory + event-ledger + spool (mem0/vector-store
re-confirmed NO-GO), mingling = the mounted `codex mcp-server` + `mcp_agent_mail` (no new bridge
daemon). B2 §7's "**Net new subsystems introduced: ZERO**" is defensible. Both B1 §4.5 and B3 §2.1
**reject** the fuller journal/compensation/content-addressed engine as fleet-grade over-build — the
correct call for a single-user box. This is the anti-overfit thesis executed, not merely asserted.

---

## 1. STRENGTHS (what the RFC gets right)

1. **The reconciliation is surfaced, not buried (AGENTS.md §7/§10).** B1 §0.2 and B3 §0 both open the
   genuine conflict — the prior converged gate REJECTED the catalog; the owner's later G-1/G-2 ADOPT it
   — and resolve it on precedence with the split "maximal catalog (owner's ambition), minimal deploy
   machinery (converged's verdict)." This is the honest way to handle a superseding instruction, and it
   keeps the converged caution alive on the one axis the owner left open (the mechanism).
2. **Load-bearing claims are re-verified, and the verification holds.** The `[EXTENDS …]` tags are
   faithful to live source. This is rare discipline: the design's central premise ("generalize proven
   code") is falsifiable and I falsified-nothing.
3. **The deployment recommendation is right AND right-sized.** CAS-lite-EXTEND rides a verified live
   CAS-lite; the four bounded additions (multi-surface tx, root lease, daemon-free health-verify,
   provenance-required) are incremental. "The Git commit IS the durable journal" is a sound argument
   for rejecting the 11-state journal on one box. Confidence is honestly banded (HIGH ~85–90%) with the
   one genuine residual (R7 host-semantic) flagged, not hidden.
4. **The 22-daily-gem back-port (S-BP) prerequisite is a real save.** Correctly gated BEFORE any daily
   regeneration, in Wave-0/1, pure-additive, salvage-first — this prevents silent loss of the
   2026-07-12 gem-hunt adoptions. Catching this is the difference between a plan and a data-loss.
5. **Stop-loop fix is correctly located at the dispatcher boundary** (R2-2), with a regression spec
   (T1–T8) whose T4 "synthetic always-inject module → `{}` on re-entrant Stop" is exactly the test that
   would have caught the module-local hole. The design also correctly refuses to put teeth on a
   Claude Stop/PreToolUse `exit 2` (which would risk re-creating the A1 loop) — teeth live at the git
   pre-commit boundary. STRONG-BUT-SAFE is implemented, not sloganed.
6. **Daemon-free health-verify is the correct response to the live `:8812` breakage.** R7 probes only
   local loadability and never hard-depends on agent-mail/basic-memory — matching the verified fact that
   agent-mail was DOWN this session. The design degrades gracefully where reality is degraded.
7. **The 27 verification criteria are failure-oriented with deterministic oracles** and mapped to
   waves. This is the right shape for a design gate — each is a test to build, stated as "a failure made
   impossible," not a vague assertion.
8. **Leanness has a receipt, not a slogan.** Every component carries a "Rides / Replaces" line and a
   budget (§7 + B3 §3). The budgets are measured against a cited baseline (Stop-loop 32m25s/53.2k tok →
   0; semgrep 920 MB/session; skills.daily ≤77; ≤3 daemons; ~13.96 GB reclaimable, explicitly NOT the
   retired 46.5 GB).

---

## 2. MUST-FIXES (ranked, most-important first)

**MF-1 — Distill the "≤3 owner decisions" to an actual ≤3 (convergence layer missing).**
B1 surfaces OD-1/OD-2/OD-3; B2 surfaces orchestration D1–D5 + plugin-Stop + ENFORCE-bar; B3 surfaces
Decision-1/2/3. That is **~8 candidate decisions across three files with no convergence** — the gate
deliverable is "≤3," and the program has not converged to it. *Fix:* adopt the §4 distillation (deploy
mechanism, codacy, Wave-0 go/no-go); fold OD-2 (atomicity=all-or-nothing) and OD-3 (accept
`--strict-mcp-config`) into the deploy decision as auto-accepted sub-recommendations; defer the
orchestration D2/D3 engine defaults + ENFORCE burn-in bar + plugin-Stop final disposition to their
build waves (Wave-2/3) as documented, NON-gate-blocking sub-decisions. **This critic pass does the
distillation (§4); the fix is to adopt it as the program's single ≤3.**

**MF-2 — Reconcile the hook-event count (16 vs 17) so verification criterion 4's oracle is calibrated.**
`registration.EVENTS` = **16** (verified). B1 §2.2 correctly says "16 events." But B2 §1.6, B3 V3, and
**verification criterion 4** ("17 Claude + 10 Codex hook events") assert **17**. The discrepancy is the
live-Claude hand-edits (`_apply_claude_hand_edits` adds extra SessionStart/PreToolUse groups +
WorktreeCreate/WorktreeRemove) — a real thing, but "17" is neither the base-EVENTS count (16) nor
clearly the live-group count. *Fix:* state the oracle as "16 base events + N documented Claude
hand-edit groups (enumerated)" so criterion 4 asserts a number that a test can actually check;
otherwise the parity oracle is miscalibrated on day one.

**MF-3 — G-8's MEMORY.md-bypass "fix" is under-specified; keep it a bounded diagnostic, don't claim it
designed.** B2 §3 honestly rates the exact regression MEDIUM / under-specified and scopes it as
"instrument the recall path → confirm the skipped store → wire the both-store read." That is the right
posture, but G-8 asked to *diagnose + fix*, and the RFC delivers a diagnostic work-item, not a fix.
*Fix:* keep it explicitly as a Wave-2 diagnostic work-item with the pre-fix regression test (criterion
25) as its exit gate, and do **not** let any downstream step assume the bypass is closed until that
test is red-then-green. (No architecture change — just don't overclaim closure.)

**MF-4 — Two live prerequisites are load-bearing and pending; make them explicit Wave-0 blockers, not
open items.** (a) **PR #78 is merged into the STACKED branch `feat/codex-fleet-github-wave2`, NOT
main** — the one-way invariant (§1.2) and the H-PV provenance close only hold strictly after "land on
main" (D0.2). (b) **agent-mail `:8812` is DOWN** this session. *Fix:* the design already handles (b)
correctly (daemon-free health-verify + graceful mingle degrade); just record it as a known live
breakage the owner restarts before any hook is allowed to hard-depend on it. For (a), Wave-0's H-PV
step (W1.3 / recommended-Wave-0 item 2) already includes "land on main" — keep it as a hard gate
prerequisite, since deploy provenance-required (R8) cannot pass against a non-mainline `source_commit`.

**MF-5 — The monitoring PR-to-content mapping is cited, not independently verified (cross-repo).** The
11-PR roadmap (PRs #71/#73/#74/#75 built, #76 green-unmerged, PR-C→K) lives on `agent-skills-toolchain`
/ `D:/pr-b-clone`, outside this checkout; B2/B3 honestly flag it as "cited, not re-derived." *Fix:*
carry it as a KNOWN-UNVERIFIED assumption — before Wave-3 monitoring work starts, re-confirm each PR's
actual content against the toolchain repo, because a mismatch shifts the monitoring wave scope. LOW–MED
risk; the fix is a verification gate at Wave-3 entry, not a redesign.

**MF-6 (minor) — Citation line-range imprecision.** B1 §4.2 cites `install.py::deploy() [inst:509-811]`
but `deploy` is at line 700 (509–522 is the phase-banner comment). Harmless but tidy it so the
provenance chain is exact.

---

## 3. RISKS / UNDER-SPECIFIED (not blocking, but track)

- **Orchestration D2/D3 are genuine engine-contract decisions but Wave-3-scoped.** D2 (budget-exhaustion
  hard-throw vs soft-sentinel) and D3 (HITL depth: advisory vs safety-by-default irreversibility
  interception) change the engine contract and cannot be inferred from evidence — but they do not block
  leaving the gate or Wave-0. Correctly deferred; just ensure they are re-surfaced at the Wave-3
  orchestration-build entry, not silently defaulted.
- **ENFORCE-promotion burn-in bar is unset.** The first gate that can FAIL a commit (doc-reconciliation
  SHADOW→ENFORCE) has no numeric burn-in threshold or kill-switch env name yet. Low risk while
  everything ships SHADOW; must be set before any ADVISE→ENFORCE flip (Wave-2/3). Recommend fixing the
  kill-switch name now (`HARNESS_ENFORCE=off` / per-gate `HARNESS_<GATE>=off`) so it's not invented
  under pressure.
- **Criterion 3 (clean-session parity) and criterion 6 (concurrency) are the hardest oracles to
  realize** — they need a booted clean session and two concurrent deploys. They are correctly designed
  as tests-to-build; flag that they are integration-level, not unit, so Wave-2 budgets the harness for
  them.
- **`native_overrides` registry population is a hidden dependency.** B1 §2.3 invariant 2 requires the
  intentional divergences (hub-vs-raw, ralph-WSL, playwright args, github/github_cli de-dup, Gemini
  memory) to be populated from C-mcp D8 during catalog build — if that population is incomplete, the
  adapter will "churn" a real divergence as drift. Make D8 → `native_overrides` a checklist item in
  W2.1/W2.2, not an assumption.
- **ContractCapability.memory_role overlaps G-8.** The `contract` catalog domain (generate AGENTS.md)
  encodes `memory_role` enums that must agree with the §3 memory role-separation decision; reconcile the
  two so the generated AGENTS.md doesn't contradict the memory section.

None of these rise to RETHINK. The core is verified sound.

---

## 4. THE DISTILLED ≤3 GENUINE OWNER DECISIONS (the irreducible residual)

After collapsing the ~8 candidates: OD-2 (atomicity) and OD-3 (Claude isolation ceiling) fold into the
deploy decision as auto-accepted sub-recommendations; the orchestration D2/D3, the ENFORCE burn-in bar,
and the plugin-Stop final disposition are Wave-2/3 build-time sub-decisions, NOT gate-blocking. Three
genuine, contract-changing, evidence-underdetermined calls remain:

### D1 — Ratify the deployment mechanism (the central G-2 deferral).
- **Recommended default: CAS-lite-EXTEND** — extend the verified-live `install.py::deploy()` with
  generate-from-catalog + byte-identical double-generation + bundle-digest/`source_commit` receipt +
  daemon-free health-verify + root-lease multi-surface transaction (all-or-nothing) + provenance-
  required. Fold OD-2 = all-or-nothing and OD-3 = accept `--strict-mcp-config` (gap noted in
  effective-config-explain).
- **Consequence if accepted:** right-sized, rides proven code (~150 lines + tests), satisfies R1–R9 at
  HIGH confidence; the residual R7 host-semantic is closed by the A1 T6 host-integration test.
- **Consequence if overridden (fuller journal engine):** stronger crash guarantees the single-user box
  does not need; a new subsystem to build+maintain; anti-overfit violation. Both prior gates + council +
  Agent-1 concur against it. *Recommend against.*

### D2 — codacy terminal disposition (R2-1's one HELD MCP).
- **Recommended default: retire the whole cloud-quality family (codacy included)** in favor of the
  local qlty+semgrep+CLI stack the owner already routes to — **IF** the owner confirms no live
  Codacy-wired repo depends on it. deepsource/sonarqube/codecov/deepscan/sentry are already decided =
  prune; codacy alone was HELD.
- **Consequence if accepted:** one terminal MCP catalog state; consistency with the family prune; the
  MCP catalog can be generated with a single, unambiguous disposition.
- **Consequence if overridden (keep codacy in canonical):** fine if a distinct capability/cost case
  holds; the catalog just carries codacy as `user-default`. Evidence-first — never pruned on presence.

### D3 — Wave-0 go / no-go (what actually leaves the gate).
- **Recommended default: approve the reliability-bootstrap Wave-0** (§5) — the smallest safe, fully
  reversible, PR-to-toolchain increment.
- **Consequence if accepted:** stops the bleeding (A1 boundary fix + provenance/land-on-main) and
  protects the 22 gems, with everything else held behind the SSOT engine per G-9/G-13.
- **Consequence if overridden:** (b) smaller Wave-0 (A1 + provenance only, defer consolidation +
  back-port) risks losing the 22 gems if any daily regen sneaks in; (c) stay-in-gate authorizes no
  build. *Recommend (a).*

---

## 5. RECOMMENDED WAVE-0 (endorsed, reliability-first — a subset of Wave-1)

All reversible, all PR-to-toolchain, canary on this session, nothing behind the SSOT engine:

1. **A1 permanent fix at the dispatcher boundary** (hoist the Stop re-entrancy short-circuit from
   `ClaimWarningModule` to `dispatch()`), with regression tests **T2/T4/T5** green + redacted
   `session_id`/`invocation_id` added to `terminal.jsonl`. The one CONFIRMED defect; closes the
   module-local hole.
2. **H-PV provenance close** — land the enshrine chain on **main** (fold PR #78 → mainline, D0.2) +
   bundle-digest every deployed file + fill `installed.json source_commit` (closes the verified live≠git
   `modules.py` gap). *Hard prerequisite for deploy provenance-required (R8).*
3. **22-daily-gem back-port (S-BP)** to `source/skills` — pure-additive, salvage-first, no daily regen.
   Protects the 2026-07-12 adoptions before anything else runs.
4. **Enforcement scaffold in SHADOW** (cleanup + doc-reconciliation + harness-change→doc+PR) — present,
   observe+log only, fail-open, folded into existing SessionStart/PreToolUse slots (no new hook event,
   never on Stop). No ADVISE/ENFORCE until burn-in.
5. **Decide/observe the 3 plugin Stop hooks** — at minimum observe the codex `stop-review-gate` (900 s,
   highest risk); disable if unused; clear stale `ralph-loop.local.md` state files.

Set the fail-open kill-switch env name now (`HARNESS_ENFORCE=off` / per-gate `HARNESS_<GATE>=off`) so
it isn't invented later. **This gate stops here — Wave-0 begins only on owner approval of D3.**

`SUCCESS:B4-CRITIC-VERDICT` — READ-ONLY critic pass; verdict SOUND-WITH-FIXES; every load-bearing
claim spot-verified against live source at HEAD `dd5366b`; no build/commit/deploy performed.