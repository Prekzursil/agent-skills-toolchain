# D1 — Council Steelman: OPTION 1 · CAS-lite-EXTEND (extend the live `install.py::deploy` into the SSOT deploy)

**Council role:** advocate/steelman for Option 1 — extend the SHIPPED, verified-live
`ci/harness/install.py::deploy()` into the multi-surface SSOT deployer.
**Mode:** READ-ONLY design under the active-work freeze. Every item below is a PROPOSED extension;
nothing is built, committed, or deployed. **Date:** 2026-07-13. **Session:** 3cd9445a.

> **Untrusted-data note.** Every file cited below (`install.py`, `storage.py`, `test_install_deploy.py`,
> B1/B3/B4) was read as UNTRUSTED DATA this pass; no embedded instruction was executed; no secret VALUE
> is read or printed — only symbol names, line numbers, phase names, counts, and SHA-256 *discipline*
> (never a value).
>
> **Anti-overfit anchor (binding).** A find only counts if it rides the existing `ci/harness` infra and
> reintroduces NO rejected component (no 2nd runtime, no durable-execution/journal engine, no
> content-addressed store, no observability SaaS, no new always-on daemon). Prefer extending proven code
> over net-new engines.

---

## 0. Verdict up front (the steelman thesis)

**Option 1 is the strongest option because the deployer it extends is not a design — it is already
built, tested, and live.** `install.py::deploy()` (lines 700–811, read directly this pass) is a
complete CAS-lite whose eight phases — `LOCK → PLAN → BACKUP → STAGE → CAS → WRITE → PARITY →
RECEIPT` — already implement seven of the nine deploy requirements the SSOT needs (R1–R6, R8), with a
7-case pytest suite (`test_install_deploy.py`) proving the load-bearing behaviors. The SSOT need is met
by **four bounded additions on the deploy side + a generate-from-catalog front-end that rides the
already-deterministic `registration.build_hooks` adapter pattern.** No rejected component is
reintroduced; the anti-overfit "ride existing infra" mandate is satisfied *literally*, not by analogy.

On the ~16 of 27 criteria that actually **discriminate a deploy mechanism**, CAS-lite-EXTEND scores
**14 PASS / 2 PARTIAL / 0 FAIL.** The two PARTIALs are (a) *clean-session parity* — which is really an
MCP-scope launch-read concern the deployer does not own — and (b) *interruption-atomicity of the
multi-file SET* — the irreducible "no atomic directory rename on Windows + no journal" gap, which is
**re-run-convergent** and does not bite a single-user box with a human who can re-run. The remaining 11
criteria are deploy-option-*agnostic* (Stop-loop boundary fix, orchestration, memory, monitoring) —
they are earned by sibling components regardless of which deploy option wins, so they neither credit nor
debit Option 1.

**The one thing this option cannot cleanly do** — make a hard-kill mid-`os.replace`-batch a single
atomic set-commit — is exactly the one guarantee a fuller journal engine would buy, and exactly the
guarantee a one-box, human-in-the-loop deploy does not need. That is the whole case.

---

## 1. What I inherit for free (the decisive fact: it is already live + tested)

`deploy()` today, per phase, mapped to the SSOT requirements (R1–R9 from `B1-RFC-core.md §4.1`) and to
the pytest that proves it:

| Phase (install.py) | What it already does | SSOT req met | Proven by (test_install_deploy.py) |
|---|---|---|---|
| **LOCK** `_acquire_deploy_lock` (615) | single-writer `.deploy.lock` per `dst`, `{pid,timestamp,iso}`, steals a lock older than 600 s | R2 (per-dst), R5 | `test_deploy_refuses_when_lock_held`, `test_deploy_steals_stale_lock` |
| **PLAN** `_managed_hashes` (590) | sha256 of every managed live file AND every candidate file; deterministic sorted walk | R4 | (implicit in CAS/parity tests) |
| **BACKUP** `shutil.copytree(…ignore=_deploy_ignore)` (746) | pre-deploy last-known-good copy, runtime-clean, only if target pre-existed | R6 | `test_deploy_parity_mismatch_restores_backup` |
| **STAGE** `TemporaryDirectory(dir=str(dst))` (750) | candidates staged on the **same filesystem** as the target → `os.replace` is atomic | R3 | happy-path |
| **CAS** re-hash-before-write (767) | re-hash each live file immediately before write; **abort the WHOLE deploy with zero writes** if any drifted since PLAN (`DeployCASConflict`) | R4 (optimistic concurrency) | `test_deploy_cas_aborts_when_live_changes_since_plan` (asserts the candidate never landed) |
| **WRITE** `os.replace(stage/rel, live_target)` (778) | per-file atomic replace; never a partial file | R3 | happy-path |
| **PARITY** re-hash live vs candidate (786) | on ANY mismatch, `_restore_tree(backup, dst)` + **fail-CLOSED** | R6 | `test_deploy_parity_mismatch_restores_backup` (live restored to known-good) |
| **RECEIPT** `_write_receipt` (675) | merge-preserve `installed.json`: `deployed_at`, `source_commit`, `target`, per-file sha256, `backup_path` | R8 (partial) | `test_deploy_receipt_records_hashes_and_extends_existing` |

Two properties from **`storage.py`** underpin the atomicity claim and are worth naming: `atomic_write_text`
(line 10) uses the canonical `write-tmp → os.replace` idiom (so even the receipt/lock writes are atomic),
and `read_json` (27) fails-soft to a default. The redaction discipline the SSOT reuses is also already
here: `_structured_diff` (192) reports **key names only, never values**, and `_summarize` (221) is
value-free — this is the seam that keeps `${VAR}` secrets out of every generated surface, receipt, and
report (criterion 24).

**The extension seam is literally pre-wired but currently inert:** `deploy(…, source_commit=None, …)`
(line 705) accepts a `source_commit` parameter that **is never referenced in the body** — the receipt
always re-derives it via `_source_commit(src)` (688), which fail-opens to `None` for a tree with no git
HEAD (proven: `test_deploy_receipt_…` asserts `receipt["source_commit"] is None`). So the provenance
extension point already exists in the signature; it just needs wiring + a fail-closed guard (ADD-4/ADD-6).
B4 independently verified this same gap ("`_source_commit` fail-opens to null", `install.py:657`).

The provider-adapter half is equally embryonic-but-real: `registration.build_hooks(provider)` is already
a **deterministic, provider-keyed** renderer for one surface (hooks), and `desired_documents()` (125)
already does the **unknown-field round-trip** (read live doc, replace only `["hooks"]`, preserve
`plugins`/`enabledPlugins`/`tasks`/`env`). The SSOT generation layer is this pattern widened from 1
surface to 6 — not a new engine.

---

## 2. What must be ADDED (precise, bounded, riding proven code)

Seven additions. Each names its seam in the live code and an honest LOC estimate. Total deploy-side
delta ≈ **250 LOC impl + ~300 LOC tests** (B1 §4.5 estimated "~150 lines + tests"; my count is higher
because I include the single-file-surface managed-set fix and pre-write candidate validation).

### ADD-1 — generate-from-catalog front-end (the SSOT source; rides `build_hooks`)
A pure `render_all(catalog, provider, live) → {surface_path: document}` that widens
`registration.build_hooks` from hooks to all six surfaces (`hooks · mcp · skills · settings · profiles ·
contract`), preserving its three proven properties: **determinism** (byte-stable render), **documented
native diffs** (typed `native_overrides`, e.g. Claude hubs vs Codex raw providers), and **unknown-field
preservation** (`desired_documents()` merge-into-live). Its output is materialized into a git-clean
*candidate root* whose per-surface subdirs become the `source_dir` of the existing `deploy()` — so
`deploy()`'s contract is unchanged; it just consumes generated bytes instead of a checked-out tree.
**Honest scope:** this is the *largest* net-new surface (typed catalog + 2 adapters × 6 surfaces +
`parity()`), but it is the G-1 generation layer, **shared by every deploy option** — it is orthogonal to
the mechanism choice. Rides `build_hooks`; ~bulk of the program, built incrementally surface-by-surface
against each live seed as its oracle.

### ADD-2 — byte-identical double-generation gate (criterion 1)
Before any deploy: run `render_all()` twice, assert `gen1 == gen2` byte-for-byte across every surface,
abort with zero writes on divergence. ~20 LOC. Rides the determinism `build_hooks` already guarantees
(the property that keeps `install.py --check` drift-free). Directly implements criterion 1's oracle
(`diff gen1 gen2 == 0`; no `Date.now()`/RNG in adapters).

### ADD-3 — root-lease ALL-OR-NOTHING multi-surface transaction (R9 + R2; the core structural add)
A `deploy_transaction(plans, *, all_or_nothing=True, root_lease_dir, …) → TxReceipt` that orchestrates N
single-surface deploys under **one harness-root lease** (hoisting the per-`dst` lock so a concurrent
`~/.claude.json` CC-exit clobber cannot interleave *between* surfaces). Ordered **leaf-first**
(mcp/skills before settings/hooks) so a partial failure degrades safely. Reasoned in full in §3.
~120 LOC + a small refactor of `deploy()`'s lock call-site to accept an externally-held lease (so the
per-dst LOCK phase nests under, or is subsumed by, the root lease).

### ADD-4 — bundle-digest + `source_commit` provenance receipt (R8; criterion 13)
Extend the receipt to a `TxReceipt`: `transaction_id`, a **whole-bundle digest** (sha256 over the sorted
per-surface per-file hashes — one Merkle-style root over the entire deployed set), a **non-null
`source_commit`** threaded from the *catalog's* committed HEAD (wiring the currently-dead `source_commit`
param through `_write_receipt`, which today ignores it), `deployed_at`, per-surface `SurfaceResult`s,
`rolled_back`, `lease_held_s`. Closes V2 (`installed.json source_commit=null`) and the live≠git blind
spot. ~20 LOC; rides `_write_receipt`'s merge-preserve.

### ADD-5 — daemon-free health-verify, at TWO points (R7; criteria 7, 11)
A per-surface `health_verify(surface, live_dir) → HealthProbe` that runs a **local, deterministic**
loadability probe and **NEVER touches a network daemon** (agent-mail `:8812` is DOWN this session;
basic-memory can wedge — so no hard dependency):
- `settings` → `json.loads(settings.json)`
- `hooks` → `subprocess dispatcher.py --event Stop` ⇒ assert stdout `"{}\n"` + exit 0
- `mcp` → `json.loads(~/.mcp.json)` + schema-validate `{mcpServers:{name:{type,…}}}`
- `skills` → `SKILL.md` front-matter parse for the changed set

Run it at **two seams**, which is the steelman upgrade over B1 §4.3 (which places it post-parity only):
1. **Pre-write, on the STAGED candidate** — so a malformed candidate is caught *before* any `os.replace`
   and **live is left byte-identical to pre-deploy** (criterion 7's exact oracle: "live untouched").
2. **Post-parity, on LIVE** — so a surface that parses in isolation but broke on landing triggers the
   compensating-restore (criterion 11).
Fail-CLOSED on a broken surface. ~60 LOC.

### ADD-6 — provenance-required precondition (R8; R1 one-way; criterion 12)
Turn the fail-open `_source_commit` into a fail-closed `require_committed_source(src) → sha | raise
DirtySourceError`: refuse to deploy if the **catalog source tree is dirty** or `git rev-parse HEAD`
yields `None`. Enforces the one-way invariant — deploy only a committed candidate; generation itself
sources from `git archive HEAD`, never the dirty working tree. ~15 LOC; inverts the existing
`_source_commit` disposition.

### ADD-7 — explicit managed-set for single-file surfaces (correctness, not optional)
`deploy()` today derives its managed set from `os.walk(root)` (`_managed_files`, 570). That is right for
the three **tree** targets (harness/skills/hooks) but **wrong for single-file surfaces** — `settings.json`,
`~/.mcp.json`, `~/.codex/config.toml`, `AGENTS.md` — where the live_dir is a *shared* directory (`~/.claude`,
`~`) whose siblings must NOT be treated as managed. Fix: parameterize the managed set with an **explicit
relpath allowlist = the keys of `render_all()`'s `{surface_path: document}` map**, so each surface manages
exactly the files the adapter rendered. This rides the generation output (no os.walk for single-file
surfaces) and is a clean, bounded change. ~20 LOC. *Calling this out is part of the honest steelman: it
is a real detail B1 §4 glossed.*

Also folded in (trivial): **`effective-config explain`** (criterion 2) — the precedence resolver from
B1 §3.4, value-free for secrets, riding `_summarize`/`_structured_diff`. Net-new command, ~80 LOC, but
part of the SSOT engine (G-10), not the deploy hot-path.

---

## 3. The multi-surface all-or-nothing transaction, reasoned from first principles

**Constraint:** Windows has **no atomic directory rename** and no atomic multi-file commit. The only
atomic primitive is same-filesystem `os.replace` on a *single* file (already exploited by STAGE's
`dir=str(dst)`). So "commit 6 surfaces as one" cannot be a single rename. Two designs, which **compose**:

**Design A — sequential compensating-restore (the B1 §4.3 sketch, simplest).**
Run `deploy()` for surface 1 (full LOCK..PARITY..RECEIPT + health-verify), then 2, … On any surface's
failure, restore ALL already-committed surfaces from their per-surface BACKUP in reverse order. Minimal
change (loop `deploy()` calls + a restore-all handler); rides the existing per-surface backup.
*Weakness:* between surface-2 committing and surface-3 failing, live is briefly mixed; a crash **during
the compensating-restore itself** can strand a partially-rolled-back set.

**Design B — global CAS-before-any-write, then batched replace-all (tighter; the task's sketch).**
Lift the phases across surfaces: (1) **stage ALL** surfaces; (2) run **pre-write candidate health-verify**
on every staged surface (ADD-5.1); (3) a **single combined CAS gate** re-hashes every managed live file
across ALL surfaces and aborts the whole batch with **zero writes** if any drifted or any candidate is
invalid; (4) **replace-all** — the full `os.replace` batch across all surfaces back-to-back, no
intervening I/O; (5) **global parity**. Because the CAS gate for the *entire* set runs before the *first*
`os.replace` of *any* surface, the "no writes if anything is wrong" guarantee holds across the **whole
set**, not just per surface. On a mid-batch `os.replace` *failure* (rare — EPERM, AV file-lock, disk
full), **reverse-replace rollback**: `os.replace` the same-fs BACKUP copies back over the already-replaced
files `[0..K-1]` in reverse; each rollback replace is itself atomic.

**Recommended: compose A+B.** Use B's global-CAS-before-any-write for the **common** failures — a
concurrent clobber or a bad candidate — which are then caught with **zero live writes** (true whole-set
all-or-nothing for those cases). Keep A's compensating-restore-from-backup only for the genuinely rare
"physical `os.replace` failed mid-batch after CAS passed." This layering shrinks the inconsistency window
to **only the replace-all loop** — a tight sequence of `os.replace` calls over ~6–20 small JSON/text files
with **no I/O or network between them** (sub-100 ms on one box).

**Two enabling adaptations (honest, non-trivial):**
- *Same-filesystem precondition.* `os.replace` is atomic only within one volume. On this box `~/.claude`,
  `~/.agents`, `~/.codex`, `~/.mcp.json` all live under `C:\Users\Prekzursil` → one NTFS volume → atomic
  across all surfaces. The STAGE-inside-dst pattern already guarantees same-fs *per surface*; the design
  must **assert same-volume** for every surface at plan time and refuse (not silently degrade) if a
  surface ever lands on another volume. LOW-confidence-if-unchecked assumption made EXPLICIT.
- *Single-file surfaces* need ADD-7's explicit managed-set, else pointing a surface's live_dir at a shared
  home dir would treat every sibling as managed.

**Why no journal is needed for recovery (the crux).** `deploy_transaction` is **deterministic +
idempotent**: re-rendering from the same `source_commit` yields identical bytes, and every surface has a
pre-deploy backup. A crash *during* the replace-all loop is recovered by simply **re-running**: the CAS
phase no-ops surfaces already at target (their live hash now equals the candidate hash equals the new
plan hash) and completes the rest. **The Git commit IS the durable journal.** An 11-state durable journal
would only add value with many concurrent writers, long-running deploys, or a multi-node fleet — none
true here.

---

## 4. Honest gaps (what this option CANNOT cleanly do)

1. **Partial-batch crash between `os.replace` calls → the rollback-from-backup window (the real gap).**
   Even with global-CAS-before-any-write, the replace-all is a *sequence* of atomic per-file replaces.
   A power-loss / SIGKILL between file K and K+1 leaves live with `[0..K]` new and `[K+1..N]` old. Windows
   offers no atomic multi-file commit to close this. **Mitigation (why it is acceptable on one box):**
   (a) the window is sub-100 ms for small config files with zero intervening I/O; (b) recovery is a
   deterministic re-run (CAS no-ops applied surfaces, completes the rest); (c) the compensating-restore
   covers the graceful `os.replace`-failure case — only a *hard kill during the loop* is
   unrecoverable-without-re-run, and a re-run always converges. This is the ONE guarantee a durable journal
   would upgrade to true crash-atomic — and the one a single-user, human-in-the-loop box does not need.

2. **Cross-surface referential consistency is ordering-based, not transactionally verified.**
   All-or-nothing guarantees the *bytes* of all surfaces commit-or-restore together; it does **not** verify
   that surface A is *semantically consistent* with surface B (e.g. `settings.json` references an MCP server
   name that the `mcp` surface must also define; a skill in `skills.daily` must exist in the skills tree).
   Leaf-first ordering shrinks the transient-inconsistency window and per-surface health-verify catches
   per-surface loadability, but a genuine cross-surface referential invariant is **not** a deploy check —
   it belongs in the GENERATION layer (`parity(catalog)` + a referential-integrity pass **before**
   generation). If a caller hand-builds `SurfacePlan`s bypassing generation, the deployer will atomically
   commit a mutually-inconsistent-but-individually-valid set. (Criterion 3/4 coverage rated accordingly.)

3. **Within-surface WRITE-loop torn state on a hard kill (pre-existing, inherited).** Even single-surface,
   WRITE is a per-file `os.replace` loop; a hard kill mid-loop tears *that one surface's* file set. Same
   re-run-convergent recovery, same no-journal trade. (Per-*file* atomicity is airtight — criterion 8; per-
   *set* atomicity against a hard kill is not — criterion 10.)

4. **Health-verify proves local loadability, NOT host-integration (R7 residual).** It proves
   `settings.json` parses and the dispatcher Stop-smoke returns `{}` — it does **not** prove a real Claude
   session boots with the deployed config. That host-semantic is closed only by a host-integration test
   (A1 T6), deferred to the enforcement B-section. So "the deployed surface actually works in a live
   session" is PARTIAL at the deploy layer by design.

5. **"Extend `deploy()`" undersells the generation breadth.** The deploy extension is genuinely small
   (~250 LOC, rides proven code). The typed catalog + 2 adapters × 6 surfaces + `parity()` +
   `effective-config explain` is the real build cost (weeks, incremental). It rides the proven `build_hooks`
   determinism pattern (no new engine), but it is not "150 lines." The steelman must not pretend otherwise —
   though this cost is **shared by every deploy option**, so it does not differentiate Option 1 vs a fuller
   engine; the *mechanism delta* is only the ~250 deploy LOC vs a new-subsystem journal engine.

---

## 5. 27-criterion scorecard (PASS / PARTIAL / FAIL, with scope honesty)

`in-scope` = the CAS-lite-EXTEND deploy/generation engine directly owns it. `delegated` = earned by a
sibling component (Stop-loop boundary fix, enforcement ladder, orchestration H6, monitoring, memory G-8);
the deploy mechanism is neutral/compatible and does NOT earn it — these 11 do **not** discriminate deploy
options.

### A. SSOT generation & parity
| # | Criterion | Rating | Scope | Justification |
|---|---|---|---|---|
| 1 | Byte-identical double-generation | **PASS** | in-scope | ADD-2 gate; adapters deterministic (rides `build_hooks` byte-stability; no `Date.now()`/RNG). |
| 2 | effective-config-explain | **PASS** | in-scope | B1 §3.4 typed resolver, per-key provenance, value-free secrets (rides `_summarize`/`_structured_diff`). Net-new but well-specified. |
| 3 | Clean-session parity | **PARTIAL** | in-scope | Deploy lands live == candidate byte-exact; but "a clean session then loads == generated (no +22 `~/.claude.json` drift-in)" depends on the MCP launch-read (D0.5) + plugin-bridge fix — outside the deployer. |
| 4 | Semantic parity | **PASS** | in-scope | `parity(catalog)` self-test (generalizes `install.py --check`) asserts set-equality of MCP names / hook events / skills. *Calibrate MF-2: "16 base events + N enumerated Claude hand-edit groups", not a bare "17".* |
| 5 | No-dup-registrations | **PASS** | in-scope | ONE writable catalog → each MCP name once/scope, exactly one owned Stop, drift-assertion in CI. Structurally prevents dups. |

### B. Deployment mechanism safety (the core discriminating group)
| # | Criterion | Rating | Scope | Justification |
|---|---|---|---|---|
| 6 | Concurrency-safety | **PASS** | in-scope | Single-writer lock (tested) hoisted to a root lease (ADD-3) serializes concurrent deploys; loser aborts with a receipt; CAS ⇒ no torn file. |
| 7 | Malformed-config recovery | **PASS** | in-scope | ADD-5.1 pre-write candidate health-verify ⇒ invalid candidate aborts before any `os.replace`; live byte-identical to pre-deploy (exact oracle). |
| 8 | Crash recovery (torn FILE) | **PASS** | in-scope | `os.replace` is filesystem-atomic ⇒ each file is old-complete or new-complete, never half-written. Airtight per-file. (Tested pattern via `atomic_write_text`.) |
| 9 | Stale-lock recovery | **PASS** | in-scope | Lock carries pid+timestamp; >600 s stolen, live owner still blocks. Directly tested (steal + refuse). |
| 10 | Interruption-atomicity (the SET) | **PARTIAL** | in-scope | Per-file atomic + re-run-convergent, but a hard kill mid-replace-batch leaves a transiently-inconsistent SET until re-run. The irreducible no-atomic-dir-rename + no-journal gap (gap #1). A fuller engine would close it — at fleet-grade cost. |
| 11 | Bad-candidate-rollback | **PASS** | in-scope | Post-write parity mismatch ⇒ `_restore_tree(backup)` ⇒ live == pre-deploy (tested); extended to multi-surface compensating-restore. |
| 12 | Deploy-from-clean-tree | **PASS** | in-scope | ADD-6 provenance-required: dirty/`None`-HEAD source ⇒ `DirtySourceError`; generation from `git archive HEAD`. |
| 13 | Receipt-provenance | **PASS** | in-scope | ADD-4 bundle digest + non-null `source_commit` (threads the currently-dead param); closes V2. |

### C. Reliability & enforcement
| # | Criterion | Rating | Scope | Justification |
|---|---|---|---|---|
| 14 | Stop-reentrancy-cannot-reproduce (boundary) | **PASS** | delegated | W1.1 dispatcher-boundary guard; deploy mechanism neutral. |
| 15 | Stop re-entrancy exit contract | **PASS** | delegated | W1.1; neutral. |
| 16 | Deliberate-live-edit-detected | **PASS** | in-scope | D2 hash receipts + `install.py --check` + live-digest≠committed-digest flags a hand-edit. Deploy-owned. |
| 17 | Harness-change-must-be-doc+PR | **PASS** | delegated | Doc-reconciliation pre-commit gate; deploy's provenance-required *reinforces* but does not earn it. |
| 18 | Gem-backport-gate | **PASS** | delegated + **hard prereq** | S-BP + no-source-adoption-fails test. **Note:** CAS-lite-EXTEND's generate-from-catalog is exactly what makes S-BP load-bearing — deploying a derived `skills.daily` before the 22-gem back-port = data loss. Deploy CREATES the hazard 18 guards ⇒ S-BP is a blocking Wave-0/1 prerequisite. |
| 19 | Cleanup-safety | **PASS** | delegated | Salvage-first cleanup hook; neutral. |
| 20 | Fail-open | **PASS** | delegated | Enforcement hooks fail-OPEN (exit 0). The deploy engine correctly fails-CLOSED on integrity — different axis, both correct. |

### D. Orchestration & cross-vendor
| # | Criterion | Rating | Scope | Justification |
|---|---|---|---|---|
| 21 | Per-agent-timeout | **PASS** | delegated | H6 helper on `parallel()`; deploy irrelevant. |
| 22 | Stall-heartbeat | **PASS** | delegated | wfmon STALL_MS; irrelevant. |
| 23 | Monitoring-parity (Codex threadId) | **PASS** | delegated | Monitoring wave; irrelevant. |

### E. Cross-cutting safety & budgets
| # | Criterion | Rating | Scope | Justification |
|---|---|---|---|---|
| 24 | Secrets-absent | **PASS** | in-scope | Catalog carries only `${VAR}`; adapters render names never values; receipt/report use proven value-free `_summarize`/`_structured_diff`. A genuine strength. |
| 25 | Both-memory-store (bypass fixed) | **PASS** | delegated | G-8 memory role separation; deploy irrelevant (keep it a diagnostic per MF-3). |
| 26 | Exactly-once-replay | **PASS** | delegated | G-8 memory spool; irrelevant. |
| 27 | Budgets enforced | **PASS** | in-scope + delegated gate | Deploy is within budget **by construction** (ZERO net-new subsystems, no daemon, seconds-long copies); the `/harness-audit` scorecard that *enforces* budgets is delegated (G-11). |

**Tally.** Overall: **27 PASS / 0 FAIL, with 2 rated PARTIAL** (3, 10). But the honest, non-inflated read
is the **16 deploy-discriminating (in-scope) criteria: 14 PASS / 2 PARTIAL / 0 FAIL.** The other 11 are
delegated and deploy-option-agnostic — they would score identically under any mechanism, so they must not
be counted as a win *for Option 1*. The two PARTIALs are the honest ceiling of this option.

---

## 6. Effort estimate

| Layer | Effort | LOC (impl + test) | Risk | Notes |
|---|---|---|---|---|
| **Deploy extension** (ADD-2..7 + `deploy_transaction`) | **LOW — ~2–3 days** | ~250 + ~300 | LOW | Rides tested `deploy()`; each ADD has a named seam; the `source_commit` param already exists. |
| **Generation front-end** (ADD-1: catalog + 2 adapters × 6 surfaces + `parity()` + explain) | **MEDIUM–HIGH — weeks, incremental** | bulk of the program | MED | Rides `build_hooks` determinism; built surface-by-surface, each proven against its live seed. **Shared by every deploy option.** |
| **Wave-0 smallest slice** (B1 §7) | ~2–3 days | — | LOW | `mcp` + `events` catalogs + their 2 adapters (oracle = regenerate exact live `build_hooks` output) + `deploy()` health-verify + provenance-required. Proves catalog→adapter→CAS-lite end-to-end on the 2 lowest-risk surfaces. |

**The decision-relevant number** is the *mechanism delta*, because the generation layer is common to all
options: **CAS-lite-EXTEND deploy = ~2–3 days on proven code; a fuller journal engine = weeks of new-
subsystem build + ongoing maintenance** for one criterion (10) upgrade the box does not need.

---

## 7. Verdict + confidence

**STRONGLY ENDORSE Option 1 (CAS-lite-EXTEND) as the deploy mechanism.** Confidence **HIGH (~85–90%)**
that it meets R1–R9 for this single-user box (matching B1 §4.5 and the B4 critic's SOUND-WITH-FIXES on
this exact shape). It is the only option that satisfies the anti-overfit mandate *literally* — the
deployer is already built, tested, and live — scores 14/16 PASS on the deploy-discriminating criteria,
and confines its two honest gaps to (a) an MCP-scope-launch concern it does not own and (b) the
irreducible set-atomicity gap that is re-run-convergent and immaterial on one box.

**The residual uncertainty is exactly, and only, the two PARTIALs:** clean-session parity (closed by the
MCP launch-read D0.5, a sibling item) and interruption set-atomicity (closed *not* by a journal but by
re-run convergence + the compensating-restore; the true host-semantic residual R7 is closed by the
deferred A1 T6 host-integration test). None justifies the fleet-grade journal/compensation/content-
addressed engine, which both prior gates, the council, and Agent-1 concur against for one box.

**Load-bearing assumptions (ledger):** (H) `install.py::deploy()` is live + tested exactly as read this
pass — HIGH, re-verified + independently confirmed by B4. (H) all six surface targets share the C: NTFS
volume so `os.replace` is atomic across them — HIGH but made an **explicit plan-time assertion** (§3), not
a silent bet. (M) the generation layer's byte-determinism holds for all six surfaces as it does for hooks —
MEDIUM, proven only for hooks today; the double-generation gate (ADD-2) turns it into a checked
invariant rather than a hope.

`SUCCESS:D1-opt1-caslite` — READ-ONLY steelman; freeze respected (no build/commit/deploy/config change);
every extension is a PROPOSED finding riding the verified-live `install.py::deploy()`.
