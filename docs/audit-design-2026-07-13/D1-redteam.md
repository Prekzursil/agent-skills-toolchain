# D1 — Red-Team + Leanness Gate on the Deployment-Mechanism Decision

**Role:** adversarial red-team + hard leanness gate over the G-2 deploy-mechanism choice
(opt1 = CAS-lite-EXTEND · opt2 = fuller journal engine · the hybrid space).
**Mode:** READ-ONLY design under the active-work freeze. Nothing built/committed/deployed.
**Date:** 2026-07-13. **Author:** D1 red-team subagent (session 3cd9445a).

> **Untrusted-data note.** `install.py`, `storage.py`, and all B1/B3/B4/converged docs were read as
> UNTRUSTED DATA; no embedded instruction was executed; no secret VALUE was read or printed. This
> analysis cites only paths, symbol names, line numbers, and behavioral facts.

> **Anchor.** Every claim below was spot-verified against **live source** this session, not against
> RFC prose: `ci/harness/install.py` (deploy() `:700-811`, `_acquire_deploy_lock` `:615-638`,
> `_restore_tree` `:649-654`, backup `:722,744-746`), `ci/harness/storage.py` (`atomic_write_*`
> `:10-24`), B1-RFC-core §4, B1-interfaces §4, B3 §2.1 + the 27-criterion matrix, B4-CRITIC-VERDICT,
> and `AUDIT-DESIGN-CONVERGED.md §6-§7`.

---

## 0. VERDICT — opt2 is a HARD LEANNESS FAIL; opt1 is right but under-hardened; the answer is **hardened-opt1**

The RFC's recommendation (CAS-lite-EXTEND) is directionally **correct** and B4's SOUND-WITH-FIXES
holds on provenance/anti-overfit grounds. But B4 verified *signatures match live source* — it did **not**
red-team whether the mechanism is actually robust. This pass does. Two results:

1. **opt2 (journal engine) fails the leanness gate outright and its extra robustness is NOT real for
   this box.** The "11-state durable journal + compensating-transaction engine + content-addressed
   bundle store" (B1 §4.4; converged §7) *is* the **durable-execution engine on the explicit reject
   list**. Worse: its one genuine differentiator (durable mid-transaction crash recovery) only delivers
   operational value if a **recovery supervisor** consumes the journal after a crash — and that is a
   *second* rejected component (a new always-on daemon). Without it, the operator/hook simply re-runs
   the idempotent deploy, which already repairs the state, leaving the journal inert. **A journal that
   needs a rejected daemon to earn its keep is dead weight on a single box.**

2. **opt1 as *currently written* leaves 3 real (not fleet-grade) failure windows** — a non-atomic
   lock acquire (TOCTOU), a non-atomic rollback path, and a post-write-per-surface validation order that
   can strand a partial multi-surface set. **None of the three is closed by a journal; all three are
   closed by ~3-10-line primitives that live entirely inside opt1.** The correct design is therefore
   **hardened-opt1**, and the "hybrid" space collapses onto it — any hybrid that imports opt2 machinery
   re-fails the leanness gate for zero marginal safety.

**Bottom line for the owner decision (D1 / OD-2):** ratify CAS-lite-EXTEND, adopt all-or-nothing
(OD-2), and fold in the 4 hardening fixes in §4. Do **not** build the journal.

---

## 1. FALSIFIED CLAIMS (load-bearing claims that do not survive contact with the source)

### FC-1 — "R1–R6 + R8 are already implemented; the mechanism is crash-safe enough" — **PARTIALLY FALSIFIED**
B1 §4.2 asserts "R1–R6 and R8 are already implemented, tested, and live." True for the **forward WRITE**
path (per-file `os.replace`, install.py:778 — atomic on Windows via MoveFileEx). **False for two of the
sub-claims it rolls up:**
- **R2 "single-writer" is not actually mutual exclusion.** `_acquire_deploy_lock` (install.py:615-638)
  checks `lock.exists()` (line 623) and then, in a *separate* statement, `atomic_write_json(lock, …)`
  (line 630). `atomic_write_json`→`atomic_write_text` (storage.py:10-24) writes a unique temp then
  **unconditionally `os.replace`s** — there is **no `O_EXCL`, no create-guard**. Two deployers that both
  observe `exists()==False` (or both observe a stale lock) both "acquire." The lock's atomicity buys a
  non-torn lock *file*, not exclusion. **R2 is guaranteed only against well-separated sequential deploys
  and stale-steal — not against a genuine concurrent race**, which is the one hazard R2 exists to stop.
- **R6 rollback is itself not crash-safe.** `_restore_tree` (install.py:649-654) restores with
  `shutil.copy2(path, target)` — an **in-place, non-atomic** stream. A crash mid-restore leaves a torn
  file, i.e. the *recovery* path is **weaker** than the forward path it recovers. "R6 implemented" is
  true in the happy path, false under a crash-during-rollback.

### FC-2 — "The Git commit IS the durable journal → re-running the deploy converges" — **FALSIFIED for one branch**
B1 §4.3 / B1-interfaces:317 rest the entire anti-journal argument on *idempotent re-run convergence*.
This holds **only when (a) the failure was transient AND (b) all candidates are validated before any
write.** The RFC's own ordering violates (b): `deploy_transaction` runs
`deploy() (LOCK…RECEIPT) → health_verify()` **per surface** (B1-interfaces:310-314), so `health_verify`
is **post-write**. Concrete counterexample on surfaces ordered `[mcp, skills, settings, hooks]`:
1. mcp written+parity+receipt (live=new). 2. skills written (live=new). 3. settings candidate is
**genuinely malformed** → fails health_verify → rollback begins → restore mcp backup → **crash before
restoring skills.** Live is now `{old mcp, NEW skills, old settings, old hooks}` — a set matching **no
commit**. Re-run: it re-plans against current live, re-captures `skills.backup = NEW skills`, keeps
failing at the malformed settings, and **never reverts the stranded new-skills to baseline.** Re-run
does **not** converge. The "Git commit is the journal" claim is only true after adding **pre-write
validate-all** (§4, fix H2) — which the RFC does not currently specify.

### FC-3 — "R2 (the ~/.claude.json multi-session clobber race) is solved by the lease Option A already has; it needs only its scope hoisted" — **PARTIALLY FALSIFIED**
B1 §4.5(3) and B4 §1.3 headline this. Two problems:
- **The deploy lease cannot serialize the actual clobber writer.** `~/.claude.json` is rewritten by the
  **Claude CLI itself on process exit**, which does not take the deploy lock. The lease serializes
  *deploy-vs-deploy*, never *deploy-vs-CC-exit*. The design tacitly concedes this elsewhere — MCP
  prune-promote is mandated **"Claude-closed only"** (B3 §2.6 row "Any"; A3:200) *precisely because the
  lease can't stop a live CC exit.* So the lease does not "solve" the named race; an **operational rule
  (deploy Claude-closed)** does.
- Even deploy-vs-deploy, the lease is the TOCTOU of FC-1. So "already solved, just hoist scope" is
  doubly overstated: the scope hoist is necessary but not sufficient (needs the O_EXCL fix), and the
  headline race is out of the lease's reach entirely.

### FC-4 — (opt2's implicit claim) "a durable journal buys crash recovery this box needs" — **FALSIFIED**
A journal earns its keep when re-derivation is expensive/impossible, the mutation is non-idempotent,
there is no clean pre-state, or a partial state is unsafe to leave *for a meaningful duration*. **None
hold here:** `git archive HEAD` re-derivation is cheap + deterministic; `os.replace` of identical bytes
is idempotent; per-surface backups exist; and the only partial-set window (§2 FW-2) is sub-second and
consumed by nothing but the next session boot. The journal's *sole* residual value — auto-repairing that
sub-second window without a manual/hook re-run — **requires a recovery daemon to read the journal**,
and that daemon is itself a rejected component. **On a box with no fleet and no recovery supervisor, the
journal provides no recovery the idempotent re-run doesn't already provide.**

### FC-5 — (meta) B4's "SOUND" is a provenance verdict, not a robustness verdict — **CLARIFIED, not falsified**
B4 §0.1 verified the `[EXTENDS …]` tags are character-for-character faithful and concluded SOUND-WITH-
FIXES. That is correct **and** narrow: B4 checked that opt1 *rides proven code*, not that opt1 *is
robust*. The failure windows in §2 were outside B4's scope. This pass supplies the missing robustness
red-team; it **reinforces** B4's anti-journal call while adding the hardening B4 did not surface.

---

## 2. REAL FAILURE WINDOWS opt1 leaves open (each: mechanism · probability · blast radius · who closes it)

| # | Window (exact seam) | Real-world probability on THIS box | Blast radius | Closed by |
|---|---|---|---|---|
| **FW-1** | **Non-atomic lock acquire (TOCTOU).** install.py:623 `exists()` then :630 `os.replace`-write; no `O_EXCL`. Two truly-concurrent deploys both acquire. | **LOW.** Deploys are manual/scripted + seconds-long; two must hit a µs-wide window. CAS (install.py:767-771) backstops most interleavings (loser aborts `DeployCASConflict`). | Torn *set* only if both CAS-pass before either WRITEs **and** sources differ → mixed config; **fully repaired by one re-run.** No torn *file* ever (os.replace). | **opt1 fix H1** (`os.open(O_CREAT\|O_EXCL)` / portalocker). **NOT a journal.** |
| **FW-2** | **Multi-surface stranded partial.** Post-write per-surface `health_verify` (B1-interfaces:310-314) + crash during compensating-restore of a *genuinely-bad* candidate → non-convergent mixed set (FC-2). | **VERY LOW.** Needs a malformed candidate **and** a crash inside the rollback of a multi-surface tx. | One session may boot a mixed config until the next deploy; with a bad candidate, re-run does **not** self-clean (FC-2). | **opt1 fix H2** (stage-all → **validate-all** → write-all → verify-all; abort with zero writes on any invalid candidate). **NOT a journal** — journal only helps if a recovery daemon (rejected) replays it. |
| **FW-3** | **Non-atomic rollback.** `_restore_tree` `shutil.copy2` in place (install.py:649-654); crash mid-restore → torn file. | **VERY LOW.** Restore runs only on the already-rare parity-mismatch/rollback branch. | One torn live file; repaired by re-run (CAS/parity). | **opt1 fix H3** (stage-then-`os.replace` the restore, mirroring WRITE). **NOT a journal.** |
| **FW-4** | **Backup stamp collision.** `stamp=…%H%M%S` (install.py:722) + `copytree(…, dirs_exist_ok=False)` (:746). Two same-second deploys of one target → `FileExistsError`, **uncaught** (only `DeployCASConflict`/`DeployLockError` are caught, :804/:730) → crash-not-graceful-fail. | **LOW-MED.** More *likely* than FW-1 to manifest the concurrency gap (same-second deploys). | No data loss (fails **before** any WRITE); one process dies with a traceback instead of a clean loser-abort. Lock is released in `finally` (:809-811) — no lock leak. | **opt1 fix H4** (µs+pid in stamp; or catch → `return 1`). **NOT a journal.** |
| **FW-5** | **Stale-steal is TTL-only, not liveness.** `_acquire_deploy_lock` steals on `now-ts > 600s` (:627) but **never checks PID liveness** — contradicts criterion 9's "steal-if-dead" and B1 §4.3 R5 "steal-if-dead." A crashed writer blocks all deploys for ≤10 min. | **LOW.** A crash mid-deploy is rare; 10-min block is annoying, not damaging. | Deploys blocked ≤600s after a crash. | **opt1 fix H4** (add `pid_exists(pid)` → steal-if-dead). **NOT a journal.** |
| **FW-6** | **Host-blind health-verify (R7 residual).** Stop-smoke proves subprocess loadability, not that a live Claude session *starts* (B1 §4.5 residual; OI-3 / A1 T6 deferred). | **MED** for a subtle settings/hook regression that parses but breaks real startup. | Next session degraded until reverted. | A **host-integration test** (A1 T6) — **orthogonal to opt1-vs-opt2; both share it.** Journal does not touch it. |

**Reading of the table:** every window with any real probability is closed by a primitive *inside
opt1*. The single window a journal is theoretically for (FW-2's durable mid-tx recovery) is closed more
cheaply by pre-write validation, and the journal's version of the fix needs a rejected daemon to run.
**Zero windows favor opt2.**

---

## 3. DISCRIMINATING CRITERIA — which of the 27 actually separate the options

Of the 27 (B3 Part 2), **22 are non-discriminating**: criteria 1-5 (generation/parity — the G-1 catalog
layer, identical under all three mechanisms), 7 & 12-13 (candidate-validation / clean-tree / provenance —
source-gates, identical), 14-27 (Stop-reentrancy, enforcement, cleanup, orchestration, memory, secrets,
budgets — nothing to do with the deploy mechanism). All three options satisfy or fail these together.

**Only 5 criteria touch deploy-mechanism robustness (6, 8, 9, 10, 11) — and NONE discriminates in favor
of opt2:**

| # | Criterion | Discriminating? | Why |
|---|---|---|---|
| **6** | Concurrency-safety ("no torn file") | **Weakly** — {naive opt1} vs {hardened opt1} | os.replace already gives "no torn **file**" for all three, so the *oracle as worded* passes on naive opt1. The deeper torn-**set** risk (FW-1) is untested by this oracle and closed by **H1 (O_EXCL) + root-lease** — inside opt1. A journal adds nothing the atomic lock + lease don't. |
| **8** | Crash recovery (mid-write torn file) | **No** | Per-file `os.replace` gives old-complete-or-new-complete for **free**; parity re-run repairs. Satisfied identically by all three. Journal redundant. |
| **9** | Stale-lock recovery ("steal-if-dead; live owner blocks") | **Weakly** — {naive opt1} vs {hardened opt1} | Shipped impl steals on **TTL**, not **liveness** (FW-5). "Live owner blocks" only holds within the 600s TTL. Closed by **H4 (pid_exists)** — inside opt1. Journals get this from lease-renewal, but the cheap fix is a PID check, not an engine. |
| **10** | Interruption-atomicity ("per-file all-or-nothing; **re-run converges**") | **YES** — {naive opt1} vs {hardened opt1} | The oracle **explicitly accepts eventual consistency via re-run** — i.e. it is calibrated to opt1's guarantee, *not* to a journal's stronger atomicity. Naive opt1 can **fail** this oracle (FC-2/FW-2 non-convergent branch); **H2 (validate-all pre-write)** makes "re-run converges" actually hold. opt2 would pass but is not *required* to pass. |
| **11** | Bad-candidate-rollback (restore-on-mismatch) | **YES** — {naive opt1} vs {hardened opt1} | Single-surface: opt1 already does it (PARITY→restore, install.py:786-795). Multi-surface + crash-in-rollback is the gap (FW-2/FW-3), closed by **H2 + H3**. Journal would also close it — at the cost of the rejected engine + daemon. |

**Conclusion:** the criteria that discriminate (10, 11, and weakly 6, 9) separate **naive-opt1 from
hardened-opt1** — they do **not** separate hardened-opt1 from opt2 in opt2's favor. The 27-criterion
matrix, read adversarially, is a case *for hardening opt1*, not for building a journal. Criterion 8 is a
free win for `os.replace`. This is the crux: **the matrix does not earn the journal a single point.**

---

## 4. SIMPLEST SUFFICIENT DESIGN that passes all 27 criteria — **hardened-opt1** (~200 LOC, one module, zero new engine/daemon)

Extend `install.py::deploy()` (the shipped, verified-live CAS-lite) with the RFC's 4 bounded pieces plus
4 red-team hardening fixes. Everything below rides existing infra; nothing reintroduces a rejected
component.

**RFC core (4) — needed for the SSOT multi-surface requirement + provenance (already in B1 §4.3):**
- **C1 · R9 multi-surface tx** — outer `deploy_transaction` over N `deploy()` calls, **all-or-nothing**
  (OD-2), reverse-order compensating-restore, surfaces ordered leaf-first (mcp/skills before
  settings/hooks).
- **C2 · R2 root lease** — one harness-root lease spanning the whole tx.
- **C3 · R7 health-verify** — daemon-free **local** loadability probe (never touches agent-mail :8812 /
  basic-memory).
- **C4 · R8 provenance-required** — fail-closed on dirty tree / null `source_commit` (turns install.py:657
  fail-open into a precondition).

**Red-team hardening (4) — each closes a verified window in §2, each 3-10 LOC, each inside opt1:**
- **H1 · Atomic lock acquire** — replace check-then-write (install.py:623/630) with
  `os.open(lock, O_CREAT|O_EXCL|O_WRONLY)` (catch `FileExistsError`) or portalocker. Makes R2 real →
  criterion 6 truly passes (closes **FW-1**).
- **H2 · Pre-write validate-ALL** — run schema/health validation on the **staged candidates** for every
  surface **before** the WRITE phase of any surface; abort with **zero writes** on any invalid candidate.
  Makes criterion 10's "re-run converges" actually hold + criterion 7 hold at the set level
  (closes **FW-2**, the only window a journal was theoretically for).
- **H3 · Atomic staged restore** — `_restore_tree` (install.py:649-654) stages then `os.replace`, mirroring
  the WRITE path, so rollback is crash-safe → strengthens criterion 11 (closes **FW-3**).
- **H4 · Collision-proof + liveness lock** — µs+pid in the backup stamp (kills the same-second copytree
  crash, **FW-4**) and a `pid_exists` check in stale-steal (steal-if-**dead**, criterion 9, **FW-5**).

**Residual (shared by all options, not a mechanism choice):** FW-6 host-semantic health (OI-3 / A1 T6) —
a host-integration test, deferred to the enforcement B-section. A journal does not close it.

**Why this is *sufficient*:** deploy-safety criteria 6-13 pass (6 via H1; 7 via H2; 8 via os.replace; 9
via H4; 10 via H2; 11 via H2+H3; 12 via C4 clean-tree; 13 via C4 provenance). Criteria 1-5,14-27 are
satisfied by the generation/reliability layers, unchanged by mechanism. **Why it is *simplest*:** it adds
no state machine, no content-addressed store, no compensating-transaction engine, no recovery daemon —
only primitives (`O_EXCL`, an ordering swap, a staged restore, a pid check) on one already-proven module.

**The hybrid space collapses here.** A "hybrid" that keeps CAS-lite for single-surface and adds a journal
for multi-surface still *builds and maintains the journal* → re-fails leanness for zero marginal safety
over H2. The only defensible hybrid **is** hardened-opt1.

---

## 5. LEANNESS VERDICT (hard gate applied)

| Option | Rides proven infra? | Reintroduces a rejected component? | Marginal safety over hardened-opt1 on THIS box | Gate |
|---|---|---|---|---|
| **opt1 (CAS-lite-EXTEND, hardened per §4)** | YES — extends `install.py::deploy()` (~200 LOC, 1 module) | **No** | — (baseline) | **PASS — adopt** |
| **opt2 (11-state journal + compensating-tx engine + content-addressed store)** | No — green-field subsystem (B1 §4.4) | **YES — the "durable-execution engine" on the explicit reject list**; and its one differentiator needs a **recovery daemon = a 2nd rejected component** | **Zero** (FC-4; §2 shows every real window is closed inside opt1) | **HARD FAIL — reject** |
| **hybrid (opt1 + partial journal)** | Partly | YES the moment any journal/CAS-store machinery is pulled in | Zero over H2 | **FAIL — collapses to opt1** |

**Anti-overfit check.** opt1(hardened) rides existing code, introduces no runtime/daemon/store, and every
addition is a primitive on a live module — it *reduces* the count of failure modes without adding a
subsystem. opt2 is the textbook anti-overfit violation the converged gate, Agent-1, the council, and B4
all already flagged (converged §7; B4 §0.3); this pass adds the decisive operational argument (FC-4: the
journal is inert without a rejected recovery daemon).

**Leanness verdict: adopt hardened-opt1; reject opt2 unconditionally; the hybrid is not a distinct
option.** The extra robustness attributed to opt2 is not real for a single-writer, single-box, git-backed,
seconds-long-copy deploy — and the four windows opt1 genuinely leaves open are closed by ~20 lines of
primitives, not by an engine.

`SUCCESS:D1-redteam` — READ-ONLY red-team; every load-bearing claim spot-verified against live source
(install.py / storage.py) this session; no build/commit/deploy performed; one deliverable written.
