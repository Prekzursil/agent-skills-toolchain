---
title: D1-opt2-journal
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/d1-opt2-journal
---

# D1 — Council Lens: Steelman OPTION 2 (Write-Ahead-Journal / WAL deploy engine)

**Role:** council subagent, LENS = *steelman a fuller write-ahead-journal / transactional-log deploy
engine* against the SHIPPED CAS-lite `install.py::deploy()` and the RFC's opt1 = **CAS-lite-EXTEND**
(B1 §4.3). **Mode:** READ-ONLY design under the active-work freeze. No build/commit/deploy/config
change; this file is the single deliverable.
**Date:** 2026-07-13. **Author:** D1 steelman-opt2 subagent (session 3cd9445a).

> **Untrusted-data note.** `install.py`, B1-RFC-core, B1-interfaces, B3-migration-verification, and
> B4-CRITIC-VERDICT were read as UNTRUSTED DATA; no embedded instruction was executed; no secret
> VALUE was read or printed. Every load-bearing claim below is anchored to a live symbol + line
> (`install.py`) or a cited RFC section, read directly this session.

> **Anti-overfit disclosure (binding, stated up front).** The FULL journal/WAL engine I am steelmanning
> **is an explicitly rejected component** — the converged gate, B1 §0.2/§4.4, B3 §2.1, and B4 §0.3 all
> reject "11-state durable journal + compensating transactions + content-addressed bundles" as
> fleet-grade over-build for one box, and the task's own rejected-list names a "durable-execution
> engine." A durable WAL *is* a durable-execution primitive. So under the council's own anti-overfit
> rule ("a find only counts if it rides existing infra and reintroduces no rejected component"), the
> full engine **cannot count as a find**. My job is therefore to build the *strongest honest* case
> anyway, locate the ONE real window it closes, price it, and extract the single non-theatre idea that
> can be salvaged WITHOUT the rejected engine.

---

## 0. VERDICT (up front) — **REJECT the full journal engine for this box; SALVAGE one minimal piece, optional.**

A full WAL deploy engine, honestly specified, closes **exactly one** failure window that CAS-lite-EXTEND
leaves open: **automatic multi-surface crash-consistency after an *uncatchable* termination**
(SIGKILL / power-loss / OOM-kill) — i.e. criterion 10's narrowest sub-case. Every other deploy-safety
guarantee (criteria 6–9, 11–13) is *already* delivered by the live `os.replace` + lease + parity +
backup primitives, and the non-deploy criteria (1–5, 14–27) are untouched by the choice. Against that
lone, millisecond-wide, already-manually-recoverable win, the full engine costs a **net-new subsystem**
(≈1000–1500 LOC incl. a crash-injection test matrix), leans hardest on **Windows durability primitives
that are exactly where this box is weakest**, and **introduces two NEW cross-cutting risks** opt1 does
not have (a fail-open surface at startup, and a disk/startup/leanness budget hit). **The Git commit
already IS the durable, content-addressed journal** — a second journal duplicates it. Confidence **HIGH
(~85–90%)**, independently corroborating four prior converged analyses; the only genuine residual is the
owner's private *weighting* of automatic crash-consistency (a values call, not a fact).

**The one salvageable idea** — automatic detection + recovery of a torn surface set on restart — can be
folded into opt1 as a **minimal intent-marker (~40–60 LOC)** that reuses the *existing* backup dir,
lock, receipt, and the `_after_stage`/`_after_write` test seams, reintroduces **no** rejected component,
and keeps "net-new subsystems = ZERO." Adopt it **only if** the owner weights the closed window above
its (low) EVPI. My steelman does **not** overturn opt1; it sharpens where opt1's single seam is.

---

## 1. THE CONCRETE DESIGN (full opt2, specified so it can be judged, not hand-waved)

A WAL deploy engine reframes the deploy as: **log intent durably → apply → on restart, replay to a
consistent terminal state.** Below is the concrete instantiation for the multi-surface SSOT case
(settings.json, hooks, `~/.mcp.json`, skills projection, AGENTS.md, Codex config — 6 surfaces × 2
providers). It *wraps* the proven inner `deploy()` rather than replacing it.

### 1.1 Journal location + format
A durable append-only log at `~/.agents/harness/deploy-journal/`, one file per transaction
`txn-<ULID>.jsonl` (ULID = lexically sortable, runtime metadata — not generated config, so the
"no `Date.now()` in adapters" determinism rule (crit 1) is untouched), plus a `CURRENT` pointer file.
Records are newline-delimited JSON so a torn *trailing* line is self-detecting (an incomplete last line
is ignored on read):

```
{"seq":0,"type":"BEGIN","txn":"01J…","source_commit":"dd5366b","surfaces":["mcp","skills","settings","hooks","profiles","contract"],"ts":…}
{"seq":1,"type":"INTENT","surface":"mcp","pre_hashes":{…},"post_hashes":{…},"backup":"backups/deploy-…/mcp"}
{"seq":2,"type":"APPLIED","surface":"mcp"}
{"seq":3,"type":"INTENT","surface":"skills",…}
{"seq":4,"type":"APPLIED","surface":"skills"}
…
{"seq":N,"type":"COMMIT","txn":"01J…"}     ← the single linearization point
```

**Durability invariant:** a transaction is durable **iff** its `COMMIT` record is present and fsync'd.
Absence of `COMMIT` ⇒ "incomplete ⇒ recover."

### 1.2 Apply
For each surface, leaf-first (mcp/skills before settings/hooks — same ordering opt1 proposes): copy
candidate→stage on the same filesystem, CAS-check live vs `pre_hashes`, per-file `os.replace` stage→live
(**identical primitive to `install.py:778`**), then append `APPLIED`. This inner loop *is* opt1's
`deploy()`, instrumented with journal writes.

### 1.3 fsync discipline (the WAL correctness core — and its Windows liability)
Write-**ahead** ordering is the entire point:
1. Append `BEGIN` + every `INTENT` (pre-image backups already on disk) → `f.flush(); os.fsync(fd)` on
   the journal file, then attempt a directory fsync so the file's *existence* is durable. **On POSIX**
   dir-fsync is real; **on Windows 11 (this box)** there is no portable directory-fsync — you rely on
   `FlushFileBuffers` (what `os.fsync` maps to on the handle) and accept weaker existence-durability.
2. **Only after** the journal is durable do the live `os.replace` writes begin.
3. After each surface's writes land → append `APPLIED` + fsync.
4. After all surfaces → append `COMMIT` + fsync (the linearization point), then retire the journal.

This is precisely where the design is *most* exposed on Windows: the same reason opt1 uses per-file
`os.replace` (B1 R3: "Windows has **no atomic dir-rename**") means a WAL here leans on durable-ordering
guarantees that Windows provides least robustly. The one OS-hazard opt1 carefully *avoided*, opt2
*re-enters*.

### 1.4 Idempotency keys
`(txn ULID, seq, surface)` + per-surface `post_hashes`. Replay is idempotent because applying a surface
= `os.replace` staged→live **only if** live-hash ≠ post-hash (skip if already at target); re-appending
`COMMIT` is a no-op. Recovery can itself crash and re-run and still reach the same terminal state.

### 1.5 Replay / rollback (recovery on restart) — the part opt1 lacks
On harness startup (a SessionStart hook) **or** at the top of the next deploy, scan the journal dir:
- No journal, or only `COMMIT`ted journals → retire them, done.
- `BEGIN` present, `COMMIT` absent → an interrupted transaction. Under a lease (recovery MUST be
  lease-guarded, same as a deploy), choose:
  - **roll-forward** (preferred, when `source_commit` is still checkoutable + unchanged): re-apply every
    surface from the recorded commit's candidate — `os.replace` where live-hash ≠ post-hash — then
    append `COMMIT`. Converges live to the intended bundle.
  - **roll-back** (when the intended bundle is no longer wanted): for each `INTENT` (whether `APPLIED`
    or not), restore its pre-image backup **via staged `os.replace`** (so the restore is itself atomic —
    this *closes opt1's non-atomic `_restore_tree` sub-gap*, see §2.3), reverse order, then retire.

### 1.6 The content-addressed bundle store (the heavyweight part — and pure redundancy here)
Full opt2 also stores each staged surface under `objects/<sha256>` so roll-forward is self-contained
(dedup + no git checkout needed). **This is the piece that is unambiguously theatre on this box:**
`source_commit` already points at git, and **git objects are already sha-256/sha-1 content-addressed** —
re-checkout from the commit is free and durable. A second content-addressed store literally duplicates
the git object database and widens the secrets-at-rest surface (§3.4). Drop it entirely even in a
steelman.

---

## 2. WHAT IT BUYS OVER OPT1 — the specific failure windows (honest, and narrow)

opt1 = CAS-lite-EXTEND already provides, from *live code*: single-writer lease (crit 6), pre-write CAS
abort-with-zero-writes (crit 6/8), per-file atomic `os.replace` (crit 8/10-per-file), post-write parity
+ restore-on-mismatch (crit 11), pre-deploy backup (crit 11), stale-lock steal (crit 9), plus the RFC's
four bounded additions (root lease, health-verify, provenance-required, bounded compensating-restore).
So I must find windows opt1 leaves open *after* all that. There are exactly two, and one is a sub-case
of the other.

### 2.1 Window A (the real one) — automatic multi-surface consistency after an *uncatchable* kill
opt1's multi-surface atomicity rests on a **compensating-restore handler**: on any surface failure,
restore all already-written backups. That handler runs on a caught exception or a **SIGINT** (Ctrl-C is
catchable — so for criterion 10 *as literally written* ("SIGINT mid-multi-file deploy"), **opt1 already
PASSES**). The gap is strictly the **uncatchable** terminations — `SIGKILL`, power-loss, OOM-killer —
where **no handler runs at all**. Then live is left a torn set: e.g. `settings.json`=new,
`hooks.json`=new, `mcp`=old-complete, `skills`=old, and the lease file stranded on disk.

opt1's recovery from that torn set is **detect-then-manual**: the drift oracle (`install.py --check` +
per-target `installed.json` digests) *surfaces* the inconsistency on the next check (crit 16), and the
owner **re-runs** the deploy — which converges, because the deployer is deterministic + idempotent
(re-PLAN against the torn live, CAS matches with no concurrent writer, WRITE re-applies the same commit
→ all-new; verified against the `deploy()` control flow at `install.py:735-803`). **But until a human
re-runs, the torn set is live-readable** — a session that boots in that window loads a config that
corresponds to **no single git commit**, which is precisely the drift-class the SSOT engine exists to
abolish.

**A WAL closes exactly this:** on the next startup, recovery reads the un-`COMMIT`ted journal and rolls
the set forward (or back) to a single-commit-consistent state **automatically, before any reader**, with
no human in the loop. That is the entire, genuine, honest marginal value: **automatic + pre-reader**
recovery of a torn multi-surface set, versus opt1's **detected + human-triggered** convergence.

### 2.2 Why that window is small (the honest counter-weight)
- The multi-surface write loop is N `os.replace` calls over ~6 small JSON/text files — **milliseconds**.
  The conditional probability of an uncatchable kill landing in that specific window, on one dev box, is
  very low.
- The torn state is **not silent**: things break loudly, the drift gate flags it (crit 16), and the
  pre-deploy backups sit on disk at `BACKUPS_DIR/deploy-<stamp>/` (`install.py:74,744`) for a one-line
  manual restore.
- Recovery is **already available**, just not automatic: idempotent re-run *or* backup restore.
- opt1 even has crashed-state hygiene today: `_is_excluded_name` ignores an orphaned `.deploy-stage-*`
  dir (`install.py:556`), so a crashed *stage* never pollutes a later deploy.
- The box's one *real* concurrency hazard — the `~/.claude.json` multi-session clobber-race (B1 R2) — is
  closed by the **lease**, not the journal; and a concurrent CC-exit rewrite mid-deploy is caught by the
  **CAS** phase (abort, zero writes), again not the journal.

So Window A is real but **millisecond-wide, low-probability, loud, and already-recoverable** — the WAL
upgrades "recover in one manual step, after detection" to "recover automatically, before a reader."

### 2.3 Window B (marginal) — atomicity of the *restore* path itself
opt1's `_restore_tree` (`install.py:649-654`) restores via **`shutil.copy2` per file — NOT atomic**. A
crash *during* a compensating-restore (or a parity-mismatch restore) can leave a live file truncated /
half-written, and opt1 has no re-entry point that knows "I was mid-restoring txn X." A WAL's rollback
uses staged `os.replace` + idempotent replay, so a crash mid-rollback simply re-runs to completion. This
is a genuine hardening — but it is **marginal** (restore only runs on the already-rare failure paths),
and it can be fixed *in opt1* by switching `_restore_tree` to stage-then-`os.replace` (a ~5-line change),
**without** a journal.

### 2.4 What it does NOT buy (so the steelman doesn't oversell)
- **Nothing** for single-file torn-write (crit 8): `os.replace` already makes every file old-complete or
  new-complete. A journal adds zero at file granularity.
- **Nothing** for concurrency (crit 6) or stale-lock (crit 9): the lease already owns these; the journal
  in fact *inherits* the same lease requirement.
- **Nothing** for malformed-config (crit 7), provenance (crit 12/13), or any SSOT-generation criterion
  (1–5) — those are the adapter/validation/receipt layers, identical under both options.
- **Nothing** for the memory exactly-once-replay (crit 26): that is the memory-spool subsystem, not the
  deploy path. (The WAL's idempotent-replay is *conceptually* the same idea, but it does not touch the
  memory spool — no code reuse across the two.)
- The "durable deploy audit trail" a journal would provide is **already** covered by the event-ledger
  (D4) + the git history of the catalog. Duplicated by existing infra.

---

## 3. HONEST COST (adversarial, not hedged)

### 3.1 New code surface — none of it battle-tested here
opt1 rides `deploy()` which is **LIVE and tested** (B3 V5; the `_after_stage`/`_after_write` test seams
exist at `install.py:707-708,759,781`). The full WAL is a **net-new subsystem**: journal writer, JSONL
torn-tail parser, apply-with-logging, replay/roll-forward/roll-back, recovery-on-restart, fsync
discipline, content-addressed store, ULID gen, `CURRENT` pointer management. Realistically **≈1000–1500
LOC incl. tests**, vs opt1's **~150 LOC + tests** (B1 §4.5). B2 §7's headline "Net new subsystems: ZERO"
flips to ONE — a first-class **leanness-gate FAIL** per the task's rejected-list ("durable-execution
engine").

### 3.2 The recovery routine is a permanent *reliability liability* on the hot path
Recovery-on-restart runs at **every** SessionStart. A bug there (a false-positive "incomplete txn"
detection, a mis-ordered rollback, a Windows fsync assumption that doesn't hold) can **corrupt a healthy
config** — turning the mechanism meant to *improve* crash-safety (crit 8/10/16) into a *new* way to
break it. The cure carries iatrogenic risk the disease (a rare, loud, recoverable torn set) does not.

### 3.3 Windows durability is the weakest-link (§1.3)
The WAL's correctness = fsync ordering + durable file-existence. Windows 11 (this box) has no portable
directory-fsync; the design's soundness rests on the OS primitive the box supports *least* robustly —
the exact hazard opt1 sidestepped by choosing per-file `os.replace`. "none-battle-tested-here" is
sharpest precisely on the correctness core.

### 3.4 Wider secrets-at-rest + budget surface
The content-addressed bundle store persists *copies* of every deployed config surface (each a new
gitleaks/redaction surface — crit 24), and the journal dir + startup scan add **disk + startup-latency**
cost against the §3.2 budgets (SessionStart latency; disk reclaim target). No new *daemon* (recovery is
startup/deploy-time, not a supervisor — daemon budget ≤3 holds), but the disk/startup/code budgets all
tighten. The store duplicates git on disk for zero marginal durability.

### 3.5 Complexity / cognitive load
opt1's deploy is one legible function whose phases map 1:1 to the requirements (B1 §4.2 banner). A WAL
adds a state machine, a recovery policy decision (roll-forward vs roll-back), and a crash-injection test
matrix at *every* seq boundary — a large, permanent maintenance tax on a single-user box that deploys
seconds-long local file copies.

---

## 4. THE 27-CRITERION SCORECARD (full opt2, with Δ vs opt1)

Ratings are for the **full journal engine**. `Δ` = change versus opt1 (CAS-lite-EXTEND). "same" = the
criterion is deploy-independent or uses an identical primitive, so opt2 neither helps nor hurts.

| # | Criterion | opt2 | Δ vs opt1 | Note |
|---|---|---|---|---|
| 1 | Byte-identical double-generation | PASS | same | adapter layer; journal is runtime-metadata, ULID not in generated config |
| 2 | effective-config-explain | PASS | same | independent of deploy |
| 3 | Clean-session parity | PASS | same (+) | recovery arguably *helps* live==generated post-crash |
| 4 | Semantic parity | PASS | same | same adapters |
| 5 | No-dup-registrations | PASS | same | drift-assertion, independent |
| 6 | Concurrency-safety | PASS | same | **lease** owns this, not the journal |
| 7 | Malformed-config recovery | PASS | same | candidate validation pre-write |
| 8 | Crash recovery (torn *file*) | PASS | **same** | `os.replace` already atomic per file — journal adds 0 here |
| 9 | Stale-lock recovery | PASS | same | pid+mtime-TTL lock |
| 10 | **Interruption-atomicity (torn *set*)** | PASS | **+ improve** | opt2's signature win: *automatic* replay-to-consistent on uncatchable kill; **opt1 = PARTIAL** on that sub-case (converges only on manual re-run; PASSES the literal SIGINT case) |
| 11 | Bad-candidate-rollback | PASS | **+ marginal** | atomic, re-runnable restore (closes opt1's non-atomic `_restore_tree`) — but opt1 can fix that in ~5 lines without a journal |
| 12 | Deploy-from-clean-tree | PASS | same | provenance-required |
| 13 | Receipt-provenance | PASS | same | `source_commit`; journal record subsumes the receipt |
| 14 | Stop-reentrancy boundary | PASS | same | dispatcher fix, independent |
| 15 | Stop re-entrancy exit contract | PASS | same | independent |
| 16 | Deliberate-live-edit-detected | PASS | same | drift gate; caveat: a buggy recovery could *be* a false editor |
| 17 | Harness-change-must-be-doc+PR | PASS | same | enforcement ladder |
| 18 | Gem-backport-gate | PASS | same | doc-reconciliation gate |
| 19 | Cleanup-safety | PASS | same | independent |
| 20 | **Fail-open** | **PARTIAL** | **− new risk** | recovery-on-restart is a NEW fail-open surface at SessionStart that opt1 does not have; PASSES *only if* rigorously fail-open (new work) |
| 21 | Per-agent-timeout | PASS | same | H6, independent |
| 22 | Stall-heartbeat | PASS | same | independent |
| 23 | Monitoring-parity (Codex by threadId) | PASS | same | independent |
| 24 | Secrets-absent | PASS | **− wider surface** | content-addressed store persists config copies at rest → more to redact |
| 25 | Both-memory-store | PASS | same | independent |
| 26 | Exactly-once-replay (memory spool) | PASS | same | WAL is conceptually aligned but does NOT touch the memory spool — no reuse |
| 27 | **Budgets enforced** | **PARTIAL→FAIL(meta)** | **− regression** | adds startup+disk+code; numeric §4 budgets strained not blown, but the **leanness/anti-bloat meta-gate FAILS** (net-new subsystem = rejected component) |

**Tally (full opt2):** 25 PASS · 2 PARTIAL (20, 27) · 0 hard-FAIL on the 27 — **but** the two PARTIALs
are risks opt2 *introduces* that opt1 lacks, the single PASS-*improvement* (10) is on the narrowest
uncatchable-kill sub-case, and the decisive rejection is the **meta leanness/anti-overfit gate**, not a
numbered criterion. Net: opt2 trades one narrow deploy-safety gain for two new cross-cutting risks + a
leanness FAIL. **A losing trade on one box.**

---

## 5. WHEN IS A JOURNAL *ACTUALLY* JUSTIFIED vs THEATRE?

**A WAL earns its keep when** (any of):
1. **Many concurrent writers / long deploys** where re-run is expensive or contended.
2. **Multi-node / fleet** — "a human re-runs it" is *not* available at each node; recovery must be
   autonomous by construction.
3. **Non-idempotent or non-re-derivable applies** — you *cannot* reconstruct the target from a durable
   source, so you must log to undo/redo.
4. **The source of truth is not already durable + content-addressed** — you need the journal to *be*
   that store.
5. **A torn intermediate state is catastrophic + unrecoverable, or safety-critical** (e.g. config that
   gates payments/authz where a torn set = an exploit window that must never be reader-visible), AND
   recovery must be automatic + pre-reader.

**It is theatre when** the deploy is idempotent, re-derivable from an already-durable content-addressed
source, seconds-long, single-writer, backed-up, loud-on-failure, and a human is present to re-run.

**This box:** one user, one box, seconds-long local file copies, **git-durable + deterministic** source,
pre-deploy backups on disk, drift-gate detection, manual re-run available, loud failure. **Every "earns
its keep" condition is FALSE; every "theatre" condition is TRUE.** The single non-theatre residual —
automatic pre-reader recovery of a torn set — is a millisecond-wide, low-probability, already-recoverable
window. **The git commit is already the durable content-addressed journal (condition 4 fails hardest):
a WAL here is a second journal shadowing the one git already gives you for free.**

---

## 6. THE SALVAGE — minimal intent-marker (the anti-overfit-respecting middle path)

If — and only if — the owner weights automatic-pre-reader crash-consistency (Window A) above its low
EVPI, do **not** build the engine. Fold a **5th bounded piece** into opt1's `deploy_transaction`:

- **On BEGIN of a multi-surface transaction**, write ONE marker: `~/.agents/harness/.deploy-txn.json` =
  `{txn, source_commit, surfaces, backup_dir, ts}` (fsync it) **before** the first surface write.
- **On COMMIT** (all surfaces parity-clean + health-verified), delete the marker.
- **On SessionStart** (folded into the *existing* slot — no new hook event, B-doc §226), a **fail-open**
  check: if the marker exists and is un-cleared, either (a) auto-restore from `backup_dir` via staged
  `os.replace`, or (b) refuse-and-warn until the owner re-runs. Fail-open: any exception → exit 0, never
  block a session.

**Why this is the salvage and NOT the rejected engine:**
- **Rides existing infra only:** reuses the current backup dir (`install.py:744`), lease
  (`_acquire_deploy_lock`), receipt (`_write_receipt`), and the `_after_stage`/`_after_write` seams to
  crash-inject in tests. **No** content-addressed store, **no** saga/compensation state machine, **no**
  11-state journal, **no** second runtime, **no** new daemon.
- **Net-new subsystems = ZERO** (a marker file + a fail-open startup check ≠ an engine).
- **~40–60 LOC + ~8–10 crash-injection tests**; ~half a day (vs 1000–1500 LOC for the full engine).
- Gets **~80% of Window A's real value** (automatic *detection* + one-step recovery of a torn set) at
  **~10% of the cost**, and pairs naturally with the ~5-line `_restore_tree`→atomic-`os.replace` fix
  (§2.3) that also closes Window B.
- Honestly, even this is **optional** — its EVPI on one box is low. It is simply the *correct place to
  draw the line* if anything from opt2 is adopted at all.

This salvage is a **strict subset of opt1's own proposed `deploy_transaction`** (B1 §4.3 piece 1 already
does a bounded compensating-restore in-process) — it merely persists a one-line marker so the restore is
recoverable *across a process death*, not just within a live handler. It is opt1-plus-a-marker, not opt2.

---

## 7. EFFORT ESTIMATE

| Option | Scope | LOC (incl. tests) | Calendar | Ongoing liability |
|---|---|---|---|---|
| **opt1 (CAS-lite-EXTEND)** | 4 bounded additions to live `deploy()` | ~150 | ~1 day | low — extends tested code |
| **Salvage (opt1 + intent-marker)** | +marker +fail-open SessionStart check +`_restore_tree` atomic fix | +40–60 | +~½ day | low — marker file, no engine |
| **Full opt2 (WAL engine)** | net-new journal/replay/recovery/content-store + Windows fsync + crash matrix | **1000–1500** | multi-day | **high** — permanent hot-path recovery routine + maintenance + leanness-gate FAIL |

---

## 8. VERDICT (calibrated)

- **REJECT the full write-ahead-journal / WAL deploy engine for this single-user box** — HIGH confidence
  (~85–90%). It is a rejected component (durable-execution engine), rides no existing infra (net-new
  subsystem), fails the leanness/anti-overfit meta-gate, re-enters the Windows durability hazard opt1
  avoided, and buys exactly ONE narrow criterion (crit 10, uncatchable-kill sub-case) that is already
  loud + backed-up + idempotently re-runnable — while introducing TWO new cross-cutting risks (crit 20
  fail-open at startup, crit 27 budget/disk) opt1 does not have. **The git commit is already the durable
  content-addressed journal.**
- **CONCUR with opt1 = CAS-lite-EXTEND** as the right, right-sized mechanism (agrees with converged
  gate, B1 §4.5, B3 §2.1, B4 §D1 — four independent analyses; this is a fifth, from the *steelman* seat,
  reaching the same place after genuinely trying to break it).
- **OPTIONAL SALVAGE:** the single non-theatre idea (automatic pre-reader recovery of a torn set) →
  the minimal intent-marker of §6, folded into opt1, adopted only on the owner's weighting. Not the
  engine.
- **Residual uncertainty:** solely the owner's private valuation of automatic crash-consistency (a
  values call). No new *falsifiable* argument surfaced for the full engine; the steelman was
  constructed in good faith and still loses on the evidence.

`SUCCESS:D1-opt2-journal` — READ-ONLY steelman; freeze respected (no build/commit/deploy/config change);
every load-bearing claim anchored to live `install.py` lines or a cited RFC section; single deliverable
written.