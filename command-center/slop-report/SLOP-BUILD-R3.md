# SLOP — BUILD lane, round 3

LANE: SLOP (build — implement and commit for real)
REPO: `C:/Users/Prekzursil/source/ast-integrate`, branch `main`
MEASURED AT: `ab3667d5` at lane start → `12f9e861` → `a144c27a` mid-run. **HEAD moved twice
under me inside ~40 minutes**, both times from a sibling lane committing to `main` in this same
worktree, so every number below carries its rev.

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died before
measuring anything and no verdict here may be cited.

## COVERAGE

| section | state |
|---|---|
| B1 twin-parity guard extended from 7 declared pairs to full-surface discovery | **SHIPPED**, executed, both-states red-proof |
| B1 direction + sync-safety of every divergent pair | **MEASURED**, 3 instruments, one of them self-corrected |
| B2 `platform/` bucket-(b) commit decision | UNKNOWN - not yet measured (this milestone) |
| B3 `$null` deletion | UNKNOWN - not yet measured (this milestone) |
| B4 duplicate-directory proposals | NOT ATTEMPTED — grounding says propose-only, and it already did |
| B5 published-command gate corpus widening | UNKNOWN - not yet measured (this milestone) |
| B6 cache + empty-dir sweep | NOT ATTEMPTED this milestone |
| frozen evidence untouched | UNKNOWN - not yet measured (this milestone) |
| the ~84 non-ruff `quality.yml` steps | NOT-CHECKED — out of this lane's reach, unchanged from grounding |

---

## B1 — the deploy-twin guard now covers 195 pairs instead of 7. SHIPPED.

### What was wrong

`ci/tests/test_deployed_hook_twin_parity.py` guarded **7 hand-listed pairs** out of a surface of
**195**. It passed, and it was doing its job *within its declared set* — which is exactly why the
27 undeclared drifted pairs were invisible. A gate that only looks at what someone remembered to
list cannot report what nobody listed.

### What shipped

The gate now DISCOVERS the surface from `git ls-files` and requires **every** discovered pair to be
byte-identical or DECLARED. Concretely:

| | before | after |
|---|---|---|
| pairs the gate can fail on | 4 | **161** (every identical pair is now a ratchet) |
| declared divergences | 3 | **34** (30 `KNOWN_DIVERGENT` + 2 `TEMPLATED` + 2 `NOT_TWINS`) |
| undeclared divergence detectable | no | **yes** — `test_no_undeclared_divergence` |
| tests | 21 | **125** |

New checks, each one closing a way the old shape could lie:

* `test_no_undeclared_divergence` — the ratchet. Pure core (`undeclared_divergences`) takes an
  injected reader so it is exercised in both states as a unit test, not only against a tree that
  happens to satisfy it.
* `test_twin_surface_discovery_is_plausible` — fail closed below 150 pairs. A discovery that
  returns nothing must not read as a clean surface.
* `test_no_stale_declaration` — a declared row that no longer matches a real twin is flagged.
* `test_templated_pair_differs_only_by_the_token` — `{{USER_HOME}}` is an exemption that must be
  *earned*: same line count, token present on the mirror side, prefix and suffix match, and one
  single consistent expansion. Otherwise "it's just templating" is a free pass anyone could write
  next to a real behaviour change in the same file.
* `test_pinned_pairs_are_not_also_declared_divergent`, `test_declared_rows_are_unique`,
  `test_declared_mirror_path_matches_its_root` — tripwires against a future failure being "fixed"
  by demoting, duplicating, or mis-pathing a row.

**Adding a row to `KNOWN_DIVERGENT` records a divergence; it does not fix one.** Every round-3 row
is prefixed `DRIFT:` and states what was measured, so no reader can mistake the list for approval.
The three pre-existing rows are prefixed `REVIEWED:`.

### Both-states proof — the gate goes RED when it should

125 green tests on a tree that satisfies them is not evidence. `_r3_redproof.py` builds a throwaway
git repo, copies the **real** gate file into it byte-for-byte, and runs it against a known-broken
surface. Nothing touches the live tree.

```
python command-center/slop-report/_r3_redproof.py
```

| probe | expected rc | actual |
|---|---|---|
| fixture repo, twins IDENTICAL → ratchet | 0 | **0** |
| fixture repo, twins DIVERGENT → ratchet | 1 | **1** |
| fixture repo (1 pair) → plausibility floor | 1 | **1** |
| fixture repo (no declared paths) → staleness | 1 | **1** |
| live tree → ratchet / floor / staleness / all 125 | 0 | **0** |

10/10. The ratchet is the only check whose verdict differs between the two fixture states, which is
what makes it a control rather than a smoke test.

### Direction of every divergence — and an instrument I had to correct mid-round

The decision that matters is not "do they differ" but **"can they be reconciled without losing
content"**. Three instruments, run in order:

1. `_r3_twinsurface.py` — enumerate + compare. **195 pairs / 161 identical / 34 differing**,
   independently reproducing the grounding round's counts from a different code path (`git ls-files -z`
   + difflib rather than that lane's probe). 5 controls pass.
2. `_r3_direction.py` — line-multiset set-difference. Reported **30 "two-way"**.
3. `_r3_direction2.py` — difflib opcodes. Reported only **3 two-way**, because a `replace` opcode
   is one edited slot, not two independent additions.

Instruments 2 and 3 looked like a refutation. **They were not, and saying so would have been the
overclaim.** `_r3_synctable.py` names the actual decision variable and resolves it: a `replace` run
means *both sides hold bytes in the same slot*, so it is exactly as content-destroying to sync as an
`insert` is. Under that definition instrument 2's **partition** was right all along and only its
LABEL was wrong; instrument 3 answered a narrower question ("independent additions") and its
`in-place-edit-only` label understated the hazard — `hooks/README.md` carries that label while
holding a 171-line block replaced by a 100-line one.

Final, decision-grade table (4 controls pass, including one proving `replace` is never scored safe):

| sync safety | pairs | meaning |
|---|---|---|
| **needs-human-read** | **30** | each side holds bytes the other lacks; a mechanical sync deletes content |
| safe mirror ← root | 3 | `rules/common/security.md`, `rules/golang/coding-style.md`, `rules/rust/coding-style.md` — mirror is a strict subset |
| safe root ← mirror | 1 | `hooks/memory-guard/test_scan.py` — root is a strict subset |

**This is why the fix is a guard and not a sync.** 30 of 34 cannot be reconciled by a script, and
the fan-out contract's C4 result is that 100% of the errors in exactly this shape of task pointed at
data loss.

### The three divergences worth a human's attention first

| pair | what was measured |
|---|---|
| `hooks/precompact-basicmemory/capture.ps1` | the repo-root copy is a **compatibility shim** whose own docstring says it exists so "an older sync or cached hook definition cannot revive the previous raw conversation capture behavior" — and the agent-self mirror **is** that previous behaviour, ~78 lines of it, still deployed by `agent-self/bootstrap.ps1:38-45`. The shim cannot suppress a copy that a different bootstrap installs over it. |
| `hooks/event-ledger/test_prune_oats.py` | the mirror keeps a 51-line `Section 5b / D-wu-25` outcome-vs-attempt-frequency test the root does not have; the root replaced the ranking assertions with the `D-n01` OBSERVED-ONLY set the mirror does not have. **Reconciling in either direction deletes real test coverage.** |
| `hooks/edit-validate/validate-stop.py` | root `hashlib.sha1(..., usedforsecurity=False)` vs mirror `hashlib.sha256(...)`, at both call sites. |

Scope on the sha1/sha256 item, stated because the grounding round rated it *likely* a
security-relevant defect: both call sites are a wrapper filename and a dedupe signature, i.e.
**non-security uses**, and the root side carries the explicit `usedforsecurity=False` annotation a
linter asks for. On that evidence it reads as a lint-driven edit applied to one tree only, not a
weakening. **UNVERIFIED**: which side changed and whether a review is recorded — settling
experiment unchanged and still unrun, `git log -S "hashlib.sha256" -- <both paths>`.

The `capture.ps1` finding is the one I would rank highest, and it is new this round.

### Evidence

```
python -m pytest ci/tests/test_deployed_hook_twin_parity.py -q     # 125 passed
python command-center/slop-report/_r3_twinsurface.py               # 195/161/34, 5 controls
python command-center/slop-report/_r3_direction2.py                # opcode profile, 4 controls
python command-center/slop-report/_r3_synctable.py                 # sync safety, 4 controls
python command-center/slop-report/_r3_redproof.py                  # both-states, 10/10
```

`python -m pytest ci/tests -q` at `a144c27a` with these changes: **781 passed, 1 skipped, 1 failed**.
The one failure is `test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`,
a Windows-only `UnicodeDecodeError` on a filename byte `0xff`. **Proven pre-existing rather than
argued**: it fails identically in a detached worktree at `HEAD` that contains none of my changes,
and `git status` shows I never touched that file, its fixture module, or `conftest.py`.

---

## CENSUS + FOUR BUCKETS, at `aff7ebad`

`python command-center/slop-report/_r3_bucketnow.py` — 6 controls pass, including the one that
caught my own detector failure (below).

| set | round 1 (`ae8205a4`) | grounding (`27da3215`) | **now (`aff7ebad`)** |
|---|---|---|---|
| tracked | 10,196 | 10,801 | **10,871** |
| untracked, not ignored | 215 | 292 | **317** |
| caches | 2,997 files / 48.9 MB | 1,729 / 47.5 MB | **2,719 / 60.1 MB** |
| empty dirs | 13 | 13 | **13** |

Untracked by tree: `command-center` 174 · `platform` 102 · `docs` 40 · `<root>` 1.

| bucket | what | disposition this round |
|---|---|---|
| **(a) committed evidence** | 45 root probes, the slop-report artifacts, `check_published_commands.py` + baseline + CI wiring | keep; **not rebuilt** |
| **(b) evidence NOT committed** | 14 `platform/` files cited by a published `python <path>` in a tracked report; 111 mention-only; my own 11 `_r3_*` probes | **14 + 11 COMMITTED this round.** The 111 mention-only remain — basename mention is the weak signal and this lane has paid for use-vs-mention three times |
| **(c) reproducible** | 2,719 cache files / 60.1 MB. **0** of the 149 `platform/`+`docs/` files qualify — not one has a tracked producer | regeneration re-demonstrated, **sweep declined this round** — see below |
| **(d) dead** | `$null` (0 B) · 13 empty dirs · 24 zero-reference files (130 KB) | **`$null` DELETED.** The rest need a quiesce point |

**A detector failure of mine, caught and fixed rather than shipped.** The first version of
`_r3_bucketnow.py` read `_g2_census.out.json` off disk. That file is a stale shell redirect —
`_g2_census.py` writes to **stdout only** and never creates it — so the probe reported
`__pycache__` at 1,676 files / 47.5 MB while the live tree held 2,666 / 60.0 MB, and nothing in it
could tell. Fixed by EXECUTING the census as a subprocess, and shipped with the control that would
have caught it: `c6_census_rev_is_current` compares the artifact's own recorded head against
`git rev-parse HEAD` and fails closed. The same control is applied to `_g2_classify.out.json`,
which is **not** re-executed — its bucket numbers are reported with their rev (`dfea977d`) and the
flag `classify_rev_is_current: false` attached, rather than passed off as current.

## B2 — the 14 `platform/` bucket-(b) files are COMMITTED, byte-unchanged

This is the dangerous bucket: files that exist on exactly one disk while three committed reports
tell a reader to run them. Measured at the CI pin `ruff@0.15.17` with the project's `ruff.toml`:

| | result |
|---|---|
| `ruff format --check` over the 14 | **rc 0** — 14/14 already formatted |
| `ruff check` over the 14, before | **rc 1** — one `F841` at `platform/lib/_p12_refute_predicate.py:107` |
| `ruff check` over the 14, after | **rc 0** |

The grounding round left this unresolved between three bad options. The one taken is a fourth:
a **per-file ignore** in `ruff.toml`, `"platform/lib/_p12_refute_predicate.py" = ["F841"]`.

* It does **not** edit evidence bytes — the objection that made option (b) unsafe.
* It is **narrower than an `extend-exclude` entry**, which is what the repo uses for
  `command-center/_*.py`. An exclusion would also drop the file out of `ruff format --check`, and
  the file is currently formatted — so an exclusion would silently license future drift in a file
  the repo now depends on. A per-file ignore keeps every other rule live.
* `published-commands-baseline.json` had already recorded this exact F841 as the reason the file
  stayed uncommitted. This removes the reason instead of re-recording it.

Control A, because "the ignore is narrow" is a claim and not an observation: the **same F841 shape
at a different path** must still be flagged. It is (`rc 1`, `F841`). Control B: the same rule on the
ignored file is silent now (`rc 0`), against `rc 1` before the edit — the two states of one pair.

## B3 — `$null` DELETED

0 bytes, untracked, `git check-ignore` rc 1 (not ignored), created 06:29 today by a PowerShell
`2>$null` redirect run under a shell that does not expand `$null`. Deleted by `_r3_apply.py`, which
refuses unless the file is both 0 bytes and untracked, then asserts absence.

Nothing can be lost from a 0-byte file, so this needs no reference scan to be safe. What it does
need is proof it disturbed nothing else: the tracked-dirty set was captured before and after and is
**identical** (`tracked_dirty_delta: []`).

`NUL` is a different file and is **not** deleted — still live, writer still unidentified (R10,
unchanged).

## B4 — duplicate directories: propose only, nothing executed

Unchanged from grounding G4 and deliberately not acted on. `tools/monitorcore/monitorcore` is
3-way identical but referenced by `.quality/charter.yml` and `quality.yml`, so identical bytes are
not evidence both consumers are dead. `tools/editor/metaswarm` and `ralph-hats/references` need
"where does this capability land afterwards" answered by an owner first.

## B5 — published-command gate corpus

UNKNOWN - not yet measured at this milestone.

## B6 — cache sweep DECLINED this round, with the reason

`_r2_bucket_c.py` re-executed: `existed_before` → `absent_after_delete` → `present_after_regen`,
`regen_rc_zero: true`, `command_does_not_dirty_tracked_files: true`. So the regenerating command is
demonstrated. Its `byte_identical_within_run` is **false** and its verdict prints
`BUCKET-C-NOT-PROVEN` — that is the already-documented `.pyc` volatility (the header embeds the
source mtime), not a new finding, and byte-identity is not the property that makes a cache safe to
delete.

Not swept anyway: **HEAD moved four times during this lane** (`ab3667d5` → `12f9e861` →
`a144c27a` → `aff7ebad`), all from sibling lanes committing to `main` in this same worktree.
Deleting 2,666 `__pycache__` files while another lane is executing Python risks a transient import
failure in someone else's run, for 60 MB of disk that is not the constraint. Honest residual, not a
silent skip — the grounding said "at a quiesce point" and this is not one.

## FROZEN EVIDENCE — UNTOUCHED

`git status --porcelain` over both frozen directories, measured by `_r3_bucketnow.py` at
`aff7ebad`: `command-center/casualty/probes` **0 dirty lines** (7 tracked),
`command-center/p2-wave/probes` **0 dirty lines** (25 tracked). No file under either path was
opened for write by this lane.

## A red gate that is NOT this lane

`python command-center/slop-report/_r2_gate_now.py --rev <rev>` at my first commit `51b98feb`:
`ruff check` rc 0, **`ruff format --check` rc 1 with 6 would-reformat**. All six are
`docs/rule-audit/*.py`, another lane's files. Run at my commit's PARENT `a144c27a`: **the same 6**.
So `gate-lint-format` on `main` was already red when I arrived and my commit added nothing to it.
Not fixed here — those look like `_<lane><n>_` evidence probes, and reformatting another lane's
evidence is the move this lane has declined twice. Remedy is theirs: format them, or add the
`ruff.toml` entry the repo already uses for that class.

## Commits

Milestone 1 — `51b98feb` `fix(twin-parity): the gate guarded 7 pairs of 195, so 27 drifted unseen`.
15 files: the gate + 13 probe/artifact files + this report. 0 foreign paths, 0 deletions.

Milestone 2 — listed once landed.
