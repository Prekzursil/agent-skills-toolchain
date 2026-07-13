# D1 — Deploy-Mechanism Recommendation (SYNTHESIS)

**Decision owed:** which mechanism the SSOT engine uses to generate + deploy the six config
surfaces (settings.json, hooks, MCP json, skills, AGENTS.md, Codex config) atomically as a set.
**Author:** synthesis architect, reconciling D1-opt1 (steelman CAS-lite), D1-opt2 (steelman
journal), D1-hybrid (H-A/B/C), D1-redteam (hardened-opt1).
**Freeze:** READ-ONLY design. No build/commit/deploy. Grounded on the live
`ci/harness/install.py::deploy()` (lines 600–811, read this session) + the four lens JSONs.

---

## 1. Recommendation (firm, ranked — no fence-sit)

**#1 — HARDENED CAS-lite-EXTEND.** Extend the SHIPPED, verified-live `install.py::deploy()`
(LOCK→PLAN→BACKUP→STAGE→CAS→WRITE→PARITY→RECEIPT) into a multi-surface all-or-nothing deployer,
and fold in the red-team's four hardening fixes (H1–H4) that close the *real* windows the shipped
code leaves open. This is the only option that satisfies the anti-overfit mandate literally (rides
proven, live-tested code; adds zero new subsystem/runtime/daemon/store), and it clears all 16
deploy-discriminating criteria once H1–H4 are in.

| Rank | Option | Verdict | One-line reason |
|---|---|---|---|
| **#1** | **Hardened CAS-lite-EXTEND** (opt1 + H1–H4) | **ADOPT** | Rides live code; ~200 LOC of primitives; closes every real window; leanness PASS. |
| #2 | #1 **+ `.deploy.inflight` marker** (H-C, ship SHADOW→ENFORCE) | Defensible add | Cheap (~40–70 LOC, no journal); upgrades the killed-process torn-SET case to auto-heal. Low EVPI on one box. |
| #3 | CAS-lite-EXTEND **+ journal *seam* for later** (H-B) | **REJECT** | Speculative Protocol abstraction; upgrades zero criteria today; bets optionality on a threat the box rejects. |
| #4 | **Full journal/WAL now** (opt2) | **REJECT** | HARD leanness-gate FAIL — reintroduces the explicitly-rejected durable-execution engine + content store; its one differentiator needs a rejected recovery daemon. |

The four lenses **converge**: every seat (including the opt2 steelman, from inside the pro-journal
chair) lands on CAS-lite-EXTEND as the mechanism and rejects the full journal. This matches the B4
critic's prior (CAS-lite-EXTEND; a fuller journal is fleet-grade over-build for one box). Five
independent analyses agreeing is a strong signal, not an echo — the opt2 steelman genuinely tried
to break opt1 and could not.

---

## 2. Why — the discriminating logic

**Of the 27 criteria, only ~5 discriminate on the deploy *mechanism*.** The red-team's cut is the
sharpest and I adopt it: criteria 1–5 (generation/parity), 12–13 (source-gates), and 14–27
(reliability/enforcement/orchestration/memory/secrets/budgets) are satisfied or failed *identically*
by every option — they belong to the generation layer and sibling components, not the deploy
mechanism. Do **not** credit any deploy option for them. The genuinely mechanism-sensitive set is:

| # | Criterion | Discriminates between | Closed by |
|---|---|---|---|
| 6 | Concurrency-safety (no torn set) | naive vs hardened opt1 | **H1** (O_EXCL lock) + root-lease |
| 7 | Malformed-config → live untouched | naive vs hardened opt1 | **H2** (pre-write validate-ALL) |
| 8 | Crash mid-write torn file | *no one* — `os.replace` is atomic for all | — |
| 9 | Stale-lock steal-if-**dead** | naive vs hardened opt1 | **H4** (pid-liveness, not TTL-only) |
| 10 | Interruption-atomicity (SET) | naive/hardened opt1 vs (marginally) journal | **H2** + re-run convergence |
| 11 | Bad-candidate rollback (cross-surface) | naive vs hardened opt1 | **H2** + **H3** (atomic staged restore) |

**The crux:** read adversarially, the 27-matrix is a case for *hardening opt1*, not for building a
journal. It earns the journal **zero** points. Every window that actually exists in the shipped code
is a missing primitive, not a missing subsystem — and I verified each against the real source:

- **FW-1 / H1** — the lock is `exists()` (line 623) *then* `atomic_write_json` (line 630), no
  `O_EXCL`: a non-torn lock *file*, not mutual *exclusion*. Fix: `os.open(O_CREAT|O_EXCL)`.
- **FW-2 / H2** — health-verify is **post-write per-surface**, so a malformed surface-N candidate
  can go live on surfaces 1..N-1 before it's caught, and a crash mid-rollback strands them. Fix:
  stage-all → **validate-ALL** → write-all → verify-all; zero writes on any invalid. This is the
  single window a journal was theoretically *for*, and H2 closes it without one.
- **FW-3 / H3** — `_restore_tree` uses in-place `shutil.copy2` (line 654): a crash mid-restore
  tears a live file, so the *recovery* path is weaker than the atomic forward path. Fix: stage-then-
  `os.replace` the restore, mirroring WRITE.
- **FW-4/5 / H4** — backup stamp is seconds-precision (line 722) + `dirs_exist_ok=False` (line 746)
  → same-second collision raises an *uncaught* `FileExistsError`; and stale-steal is **TTL-only**
  (line 627), never checks pid liveness, contradicting criterion 9. Fix: µs+pid stamp; steal-if-dead.

**Provenance is a free win already wired.** `deploy(... source_commit=None ...)` (line 705) is a
**dead parameter** — the receipt re-derives via `_source_commit` (line 687), which fail-*opens* to
`None` (lines 657–672). Thread the real commit through and invert the fail-open to a
`require_committed_source` precondition → criteria 12/13 pass with ~15 LOC on an existing seam.

**Why the full journal (opt2) loses on one box** (the decisive operational argument): a journal
earns its keep only with expensive/non-idempotent re-derivation, no clean pre-state, or a partial
state unsafe for a meaningful duration. **None hold here:** `git archive HEAD` re-derivation is
cheap+deterministic (the git commit *is* the durable content-addressed journal); `os.replace` of
identical bytes is idempotent; per-surface backups already exist; the only torn-SET window is
sub-second and consumed only by a session boot. The journal's sole residual value — *automatic*
repair without a re-run — requires a **recovery daemon** to replay it, itself a rejected component.
Without that daemon the operator re-runs the idempotent deploy (which already repairs), leaving the
journal inert. So opt2 buys one narrow criterion-10 sub-case at the cost of a ~1000–1500 LOC net-new
subsystem, a permanent hot-path recovery liability, a Windows dir-fsync soundness dependency (the
exact durability primitive this box supports *least* robustly), a wider secrets-at-rest surface, and
a first-class **leanness-gate FAIL**. That is losing on one box.

---

## 3. Design sketch — Hardened CAS-lite-EXTEND

Keep the proven single-surface `deploy()` intact; wrap N of them in a root-leased transaction and
apply the four hardening fixes. Every addition is a primitive on a live module.

```
deploy_transaction(plans, *, all_or_nothing=True, root_lease_dir):
  # C2  ONE harness-root lease spanning the whole tx (hoists _acquire_deploy_lock;
  #     H1: acquire via os.open(O_CREAT|O_EXCL|O_WRONLY), catch FileExistsError;
  #     H4: stale-steal only if pid is dead, not merely TTL-expired)
  with root_lease(root_lease_dir):
      # C4  provenance-required: refuse a dirty / None-HEAD source (invert line 657
      #     fail-open into require_committed_source -> DirtySourceError). Generate
      #     surfaces from `git archive HEAD` only. Threads the DEAD source_commit param.
      assert_same_volume(plans)          # os.replace atomicity precondition (all under C:)

      # order leaf-first: mcp / skills BEFORE settings / hooks (referential safety)
      for p in plans: p.backup()         # existing BACKUP phase, per surface
      for p in plans: p.stage()          # existing STAGE (same-fs temp)

      # H2  validate-ALL the STAGED candidates before ANY write (C3 health-verify:
      #     LOCAL loadability only — settings->json.loads, hooks->dispatcher --event Stop
      #     asserts {}/exit0, mcp->json.loads+schema, skills->front-matter. NEVER touches
      #     agent-mail:8812 / basic-memory). Abort with ZERO writes if any surface invalid.
      for p in plans: p.health_verify_staged()

      # single combined CAS gate across ALL surfaces' live files (existing pre-write CAS,
      # lifted to the batch): if any drifted since PLAN -> abort whole batch, zero writes.
      for p in plans: p.cas_check_or_abort()

      # WRITE: batched per-file os.replace, no intervening I/O; then global PARITY.
      try:
          for p in plans: p.write()      # existing atomic per-file replace loop
          for p in plans: p.parity_or_raise()
      except Exception:                  # graceful failure -> compensating restore
          for p in reversed(applied): p.restore_from_backup()  # H3: staged-then-replace
          raise
      # RECEIPT (C: bundle digest): TxReceipt{transaction_id, whole-bundle sha256 merkle
      # root, NON-null source_commit, per-surface results} merged into installed.json.
```

**Managed-set correctness (real detail, not optional):** parameterize `_managed_files` with an
explicit relpath allowlist = the keys of the generator's `surface_path` map, so single-file surfaces
(settings.json, .mcp.json, config.toml, AGENTS.md) don't sweep shared-dir siblings. `os.walk` is
right only for the three tree targets.

**Effort:** deploy extension ~200 LOC + ~300 tests, **LOW risk / ~2–3 days**, each fix on a named
seam. Crash-injection tests reuse the existing `_after_stage` / `_after_write` seams (lines 707–708,
759–782). The **generation front-end** (typed catalog + 2 adapters × 6 surfaces + `parity()` +
explain) is the bulk of the program — **weeks, incremental** — but it is **shared by every deploy
option**, so it does not differentiate this choice.

---

## 4. Honest tradeoff (what #1 does NOT give you)

The one guarantee hardened-opt1 does not upgrade: after an **uncatchable** termination
(SIGKILL / power-loss / OOM-kill) *between* the per-file `os.replace` calls of a multi-surface
batch, live is left a torn SET (some surfaces new, some old) corresponding to no single git commit.
No in-process handler runs, so the compensating-restore can't fire. Recovery is **detect-then-
re-run**: the drift oracle (`install.py --check` + `installed.json` digests, criterion 16) surfaces
it and the owner re-runs — which, with H2 in place, **always converges forward** to the fully-
deployed state (CAS no-ops the applied surfaces). The torn set is live-*readable* until a human acts.

On a single, human-in-the-loop developer box, the delta between "detected + one re-run away" and
"automatically healed before any reader" is **low EVPI** — Windows has no atomic multi-file commit,
the window is sub-100ms for small config files with zero intervening I/O, and re-run is deterministic.
That is precisely the gap the **H-C `.deploy.inflight` marker** (RE-ASK option B) closes cheaply
(~40–70 LOC, no journal, no persistent stage — the backups + committed source are the durable
anchors already on disk; the marker is the same *category* as the existing `.deploy.lock`). It is a
defensible add, **not** a leanness violation. My call: adopt #1 now; take the marker's *detection*
half essentially free in SHADOW (log an orphaned marker, never auto-heal), and only wire the
auto-heal (rollback-to-baseline vs re-run-forward) if a real torn set is ever observed — auto-heal on
every SessionStart is the one place a bug could iatrogenically corrupt a *healthy* config.

**Two calibrations to carry forward** (verified this session): (a) the parity oracle's event count —
`registration.EVENTS` = 16, not 17; state it as "16 base + N enumerated hand-edit groups". (b)
Assert same-volume at plan time (all six surfaces under `C:\Users\Prekzursil`) and **refuse** rather
than silently degrade if a surface ever lands off-volume — `os.replace` atomicity depends on it.

---

## 5. RE-ASK options for the owner

**A — Pure Hardened CAS-lite-EXTEND (recommended default).** Ship opt1 + H1–H4 (root-lease,
O_EXCL lock, validate-ALL, atomic restore, steel-if-dead, provenance-required). Killed-process
torn-SET recovery is detect + one idempotent re-run. Leanest; ~2–3 days on the mechanism. Add the
`.deploy.inflight` marker's **SHADOW detection** for free (log-only) so drift is loud.

**B — A + `.deploy.inflight` auto-heal (belt-and-suspenders).** Everything in A, plus the H-C marker
wired through OFF→SHADOW→ADVISE→ENFORCE so an uncatchable kill auto-heals the torn SET (rollback for
`all_or_nothing`, else re-run-forward) *before* a reader. +~0.5 day, +~5 crash-injection tests, still
zero new subsystem. Choose if you weight automatic crash-consistency over its low EVPI on one box.

**C — A + a journal *seam* for later (H-B).** Ship A's behavior wrapped in a formal Transaction
Protocol so a journal backend could slot in if a real failure ever demands it. Upgrades no criterion
today; pays a standing abstraction now for a future the one-box threat model rejects. **Not
recommended** — `deploy_transaction` is already a plain function you can extend later without the
speculative Protocol.

**D — Full journal/WAL now (opt2).** Build the durable write-ahead journal + recovery-on-restart now.
**Not recommended** — HARD leanness-gate FAIL, Windows-fsync soundness risk, permanent hot-path
recovery liability, and its sole differentiator needs a rejected recovery daemon. Listed only so the
rejection is on the record as a deliberate choice.

> My firm pick: **A now, with the marker's SHADOW detection folded in; escalate to B only if a real
> torn SET is ever observed.** This threads the leanness gate, closes every window that actually
> exists in the shipped code, and keeps the auto-heal risk out of the hot path until evidence
> demands it.
