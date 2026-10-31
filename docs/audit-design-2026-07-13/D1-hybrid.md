---
title: D1-hybrid
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/d1-hybrid
---

# D1 — Hybrid Architect Verdict (combination / both+extension lens)

**Role:** the HYBRID architect the owner explicitly asked for — "a combination of both, or both+extension."
**Mode:** READ-ONLY design under the active-work freeze. Every proposal below is PROPOSED; nothing is
built, committed, deployed, or configured.
**Date:** 2026-07-13. **Author:** D1 hybrid subagent (session 3cd9445a).

> **Untrusted-data note.** B1-RFC-core, B1-interfaces, B3-migration-verification, B4-CRITIC-VERDICT, and
> the live `ci/harness/install.py` were all read as UNTRUSTED DATA. No embedded instruction was executed;
> no secret VALUE was read or printed. This verdict cites only paths, symbol names, line numbers, and the
> 27-criterion IDs from B3.

> **Baseline (opt1) for this whole document = CAS-lite-EXTEND** (B1 §4.3 Option A) — the RFC's own
> recommended mechanism: extend the verified-live `install.py::deploy()` with four bounded pieces
> (multi-surface transaction, root lease, daemon-free health-verify, provenance-required). The hybrid
> lens does NOT re-litigate opt1 vs a full journal (B1 §4.5 + B3 §2.1 + B4 §4-D1 already settled that:
> the 11-state journal is fleet-grade over-build for one box). It asks the narrower question the owner
> posed: **is there a `both+extension` shape that upgrades opt1 at a cost worth paying?**

---

## 1. Where opt1 is genuinely PASS, and the ONE honest residual gap

opt1 is strong. Grounded in the live code, it already earns PASS on most of B3's Group-B deployment
criteria **without any hybrid**:

| B3 crit | Why opt1 already PASSes | Live anchor |
|---|---|---|
| #6 Concurrency-safety | root-lease hoist of the single-writer `.deploy.lock` serializes deploys | `_acquire_deploy_lock` `install.py:729` |
| #7 Malformed-config | health-verify fail-closed after parity; broken surface reverts to backup | B1 §4.3(3) |
| #9 Stale-lock | lock carries pid+mtime; 600 s stale-steal; live owner still blocks | `DEPLOY_LOCK_STALE_SECONDS`, `:706` |
| #12 Deploy-from-clean-tree | provenance-required refuses a dirty/`source_commit=null` tree | `_source_commit` `:657`→precondition |
| #13 Receipt-provenance (steady) | per-surface `installed.json` digest + non-null `source_commit` | `_write_receipt` `:675-693` |
| #8/#10/#11 **per-file** | per-file `os.replace` = each file old-complete or new-complete; parity restores on mismatch | `os.replace` `:778`, restore `:786-795` |

**The one residual gap the hybrids target — the *multi-surface* atomicity of a *killed* process.** opt1's
all-or-nothing is a **compensating-restore executed in-process** (B1 §4.3(1)): "on ANY surface failure,
restore ALL already-written surfaces' backups." That is sound for a *caught exception*. It is **not**
sound for a hard process death (SIGKILL, OOM, power loss) landing between surface *k* and surface *k+1*
of a batch, because:

1. **No in-process code survives to run the compensating-restore.** The recovery story degrades to
   B1-interfaces §4's docstring — *"re-running no-ops surfaces already at target"* — which rolls the batch
   **FORWARD**, never back. If the batch was meant all-or-nothing and the operator does **not** re-run
   (abandons the deploy, or wanted to back the new catalog out), live is left silently **torn**:
   surface *k* = new, surfaces *k+1…N* = old.
2. **Nothing durable records that a batch was in flight.** `TxReceipt` is a **return value** (B1-interfaces
   §4) — it exists only if `deploy_transaction` *returns*. A killed process persists **no** transaction
   record. Each surface's own `installed.json` is written only on *that* surface's success
   (`install.py:798`), so post-crash you get a fresh receipt on surface *k* and stale receipts on the
   rest, with **no** tie-breaker saying they belonged to one aborted batch.
3. **The stage is gone.** STAGE is a `tempfile.TemporaryDirectory` (`install.py:750`) auto-wiped on
   context exit / crash — so there is nothing on disk to "finish writing" from either.

So B3 **#10 (Interruption-atomicity)** and the multi-surface angle of **#8/#11** are honestly **PARTIAL**
for opt1: PASS for a caught exception, but the *killed-process* sub-case relies on an operator remembering
to re-run, and even then only rolls forward. The oracle for #10 says *"receipt records partial +
resumable"* — but opt1's receipt is not persisted on a hard crash, so "resumable" is not actually
guaranteed. **This — and only this — is what a hybrid should close.** Everything else is gold-plating.

---

## 2. The three hybrids, reasoned against the live code and the anti-bloat gate

### H-A — CAS-lite core + a MINIMAL journal around the multi-surface commit

**Design.** Before the batch WRITE phase, journal the replace-batch *intent* (the ordered
`staged_path → target_path` + `expected_hash` list); clear it on success; on the next run, replay-or-roll
the journal deterministically. "Journal the risky 200 ms, not the whole pipeline."

**Criteria it upgrades:** #8, #10, #11 (multi-surface killed-process sub-case) PARTIAL→PASS.

**Fatal cost / anti-overfit verdict — REJECT.** A journal that can *replay the write* must replay from
**staged bytes**, but the live STAGE is a `TemporaryDirectory` destroyed on crash (`install.py:750`).
H-A therefore forces a **persistent staging area that outlives the process** + journal write + replay
logic + journal GC + stale/corrupt-journal handling + a replay-vs-rollback policy engine. That is no
longer "~150 lines riding proven code" — it is the **seed of the exact durable-execution engine the task
lists as a REJECTED component** and that B4 §4-D1 / B3 §2.1 / B1 §4.5 all rejected. It rides existing
infra *less* than opt1 and reintroduces a rejected concept. A find "only counts if it reintroduces no
rejected component" — H-A fails that gate.

### H-B — Staged evolution: ship opt1 now behind a `Transaction` seam for a future journal backend

**Design.** Ship CAS-lite-EXTEND, but wrap it in a formal `Transaction` Protocol so a journal backend can
slot in later IF a real failure demands it. YAGNI-with-an-escape-hatch.

**Criteria it upgrades:** **ZERO today** — it ships opt1's exact behavior.

**Cost / verdict — REJECT.** It upgrades no criterion now, adds an abstraction layer (interface + default
impl) with a standing maintenance cost, and bets the optionality on a backend the threat model *rejects*
(one user, one box, seconds-long local copies — B1 §4.4). Worse, the seam is **already implicit**:
`deploy_transaction` is a plain function composing N `deploy()` calls (B1-interfaces §4); you can always
add a marker or journal later without a speculative Protocol. H-B pays indirection now for a future the
evidence says will not come — the precise YAGNI it claims to avoid.

### H-C — CAS-lite-EXTEND + a lightweight `.deploy.inflight` crash-recovery marker  ← **CHOSEN**

**Design.** opt1 exactly as specified, PLUS a single write-once/delete-once breadcrumb, scoped **only** to
the multi-surface `deploy_transaction` (a single `deploy()` needs none — one file is already atomic and
cannot leave a torn *set*). Concretely:

- **At batch start, before the first surface WRITE**, atomically write `~/.agents/harness/.deploy.inflight`
  — a small JSON manifest:
  ```
  { transaction_id, source_commit, all_or_nothing,
    owner_pid, started_at,                       # stale-steal semantics, exactly like .deploy.lock
    surfaces: [ { surface, target_dir, backup_path } , … ] }   # backup_path already produced by BACKUP
  ```
  It records **pointers to durable anchors that already exist** — the per-surface backups from the live
  BACKUP phase (`BACKUPS_DIR`, `install.py:744`) and the committed `source_commit`. It does **NOT** journal
  staged bytes, so it needs **no** persistent stage.
- **On batch success**, unlink the marker and let the existing per-surface receipts + returned `TxReceipt`
  stand.
- **On any harness/deploy entry**, `recover_inflight()` runs first: if a marker exists, it is
  **classify-first and idempotent** — for each surface it compares live-hash vs committed-target-hash vs
  backup-hash to label {at-target | at-old | torn}. If every surface is at-target → clear marker (no-op,
  the batch actually finished). If every surface is at-old → clear marker (no-op). It **acts only on a
  genuinely torn set**, applying the manifest's declared policy: `all_or_nothing=True` ⇒ ROLL BACK
  (restore each not-already-old surface's listed backup via the existing `_restore_tree`, `install.py:649`)
  returning live to the pre-batch baseline; a roll-forward policy ⇒ re-run `deploy_transaction` from
  `source_commit`. Then write a recovery receipt and delete the marker.
- **Ship it through the RFC's own OFF→SHADOW→ADVISE→ENFORCE ladder** (B3 §2.0 rail 3): SHADOW = detect +
  log an orphaned marker, never auto-heal; promote only after a zero-false-heal burn-in. So H-C is
  strictly additive and cannot make anything worse than opt1 while it burns in.

**Why H-C dominates H-A (the decisive anti-bloat argument).** H-C buys the *same* recovery guarantee as
H-A — a killed process's torn batch is auto-detected and resolved on the next run — but WITHOUT a byte
journal and WITHOUT a persistent stage, because it recovers from the **two durable anchors already on
disk**: the backups (for rollback) and the committed source (for idempotent roll-forward re-render). A
write-once/delete-once breadcrumb that is classified idempotently is the **same category as the existing
`.deploy.lock`** (pid+ts, stale-stealable) — it is emphatically **not** a durable-execution engine (no
state machine, no replay queue, no byte log). It reintroduces **no rejected component**; H-A reintroduces
one.

**Why H-C is not gold-plating over opt1.** It closes the one criterion opt1 leaves honestly PARTIAL (#10
killed-process), and it is the *smallest possible* mechanism that does so. It is best understood not as a
new axis but as **the honest completion of the RFC's own OD-2** (B1 §6): OD-2 recommends all-or-nothing via
"bounded compensating-restore," but that restore only runs if the process lives. H-C is the minimal thing
that makes the *already-chosen* all-or-nothing actually hold across a process death too. It adds no new
decision — it makes OD-2's recommended answer true.

---

## 3. Decision matrix

| Axis | opt1 (CAS-lite-EXTEND) | H-A journal | H-B seam | **H-C marker (CHOSEN)** |
|---|---|---|---|---|
| Multi-surface killed-process atomicity (#8/#10/#11) | PARTIAL (operator re-run, forward-only) | PASS | PARTIAL (= opt1) | **PASS** |
| Criteria upgraded vs opt1 | — | 3 | **0** | **3 (+1 minor)** |
| Reintroduces a REJECTED component? | No | **YES (durable journal + persistent stage)** | borderline (speculative engine seam) | **No** (breadcrumb ≈ existing lock) |
| Rides existing infra | — | LESS than opt1 | = opt1 + indirection | **= opt1 + one file** |
| Incremental cost over opt1 | — | HIGH (new subsystem) | LOW-but-useless | **LOW (~40-70 LOC, verified helpers)** |
| Reversible / SHADOW-able | — | hard (stateful) | n/a | **YES (SHADOW→ENFORCE ladder)** |
| Anti-bloat gate | pass | **FAIL** | FAIL (YAGNI) | **PASS** |

---

## 4. Criteria upgraded PARTIAL→PASS by H-C (mapped to B3's 27)

- **#8 Crash recovery (multi-surface angle)** — opt1: per-file atomic PASS, but a torn *set* after a hard
  crash only "re-runs forward," operator-dependent. H-C: durable pre-write marker → next entry
  auto-detects + heals (forward or back per policy) with no operator memory. **PARTIAL→PASS.**
- **#10 Interruption-atomicity** — opt1: "resumable" holds for a caught exception but not a killed process
  (no `TxReceipt` persisted on hard crash). H-C: the marker persists intent + backup pointers *before* the
  risky WRITE, so a killed process is genuinely resumable/reversible. **PARTIAL→PASS** (closes exactly the
  oracle's "receipt records partial + resumable" for the kill case).
- **#11 Bad-candidate-rollback (cross-surface)** — opt1: PASS for in-process parity mismatch, but a killed
  process that already parity-passed surface *k* leaves a torn set with no rollback. H-C: marker lets the
  next run roll the whole SET back to baseline under `all_or_nothing`. **PARTIAL→PASS.**
- **(minor) #13 Receipt-provenance** — strengthened from steady-state-only to a **durable
  transaction-level recovery receipt across interruption** (an interrupted batch leaves a recovery record,
  not silence). PASS→PASS+.

Criteria H-C does **not** touch (opt1 already PASS, H-C rides it): #6, #7, #9, #12. Note H-C's marker
reuses the lock's pid+mtime **stale-steal** so an abandoned marker is distinguished from a live batch —
so it does not regress #9.

---

## 5. Incremental cost over opt1 (honest accounting)

All net-new code assembles **verified-present** helpers; nothing is invented:

| Piece | Implementation | Reused live helper (verified) |
|---|---|---|
| `write_inflight_marker(...)` | one atomic JSON write before first surface WRITE | `atomic_write_json` `install.py:692` |
| `clear_inflight_marker()` | safe unlink on success | `_release_deploy_lock`-style `:641-646` |
| `recover_inflight() -> RecoveryReceipt` | classify {at-target/at-old/torn} → roll back or forward | `_hash_file` `:737`, `_managed_hashes` `:738`, `_restore_tree` `:649`, `deploy_transaction` re-run |
| entry hook | call `recover_inflight()` at `deploy_transaction` start + a SHADOW SessionStart probe | folds into existing SessionStart slot — **no new hook event / daemon** (B3 §3.2 budget) |
| tests | crash-inject a raise between surfaces, assert next entry heals | **existing `_after_stage`/`_after_write` seams** `:707-708,759-782` |

**Estimated incremental cost over opt1: ~40-70 LOC + ~5 tests.** **Zero** new infra: no persistent stage,
no journal, no new dependency, no new daemon (stays ≤3, B3 §3.2), no new hook event, no rejected component.
It sits *inside* opt1's four additions rather than beside them — the marker is written in the same
root-lease critical section opt1 already establishes.

---

## 6. Verdict

**Adopt H-C: CAS-lite-EXTEND + a `.deploy.inflight` crash-recovery marker, scoped to the multi-surface
transaction, shipped through the existing SHADOW→ENFORCE ladder.**

It is the only `both+extension` shape that (a) upgrades a genuinely-PARTIAL criterion (#10 killed-process
multi-surface atomicity, plus #8/#11 sub-cases) to PASS, (b) does so at the lowest incremental cost
(~40-70 LOC assembling verified-present helpers), (c) reintroduces **no** rejected component (a write-once
breadcrumb is a sibling of the existing `.deploy.lock`, not a durable-execution engine), and (d) is
strictly additive + reversible via the RFC's own enforcement ladder. H-A is rejected for reintroducing a
durable journal + persistent stage (the rejected component, higher cost, same coverage as H-C); H-B is
rejected for upgrading zero criteria while adding speculative indirection (YAGNI) for a backend the threat
model rejects.

**Framing for the owner gate:** H-C is not a new owner decision — it is the **minimal honest completion of
OD-2** (all-or-nothing), making the RFC's already-recommended atomicity hold across a process death, not
only a caught exception. It can be folded into Decision 1 (deploy mechanism) as an auto-accepted
sub-recommendation, gated OFF→SHADOW at first.

**Confidence: HIGH (~85%)** that H-C closes the killed-process multi-surface gap at the stated cost with no
rejected-component reintroduction. The residual ~15% is the same host-semantic residual opt1 carries (R7):
the classify-and-heal routine proves local hash convergence, not that a live Claude session *restarts*
clean after a recovery — closed by the same A1 T6 host-integration test the RFC already defers.

`SUCCESS:D1-hybrid` — READ-ONLY hybrid design; three hybrids reasoned against live source at the deploy
seam; chosen H-C; no build/commit/deploy/config change performed; every load-bearing extend-point cited to
`install.py` line numbers verified this session.