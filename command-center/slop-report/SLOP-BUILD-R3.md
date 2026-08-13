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
| B2 `platform/` bucket-(b) commit decision | **SHIPPED** — 14 committed byte-unchanged, both states controlled |
| B3 `$null` deletion | **SHIPPED** — deleted, zero collateral proven |
| B4 duplicate-directory proposals | NOT ATTEMPTED — grounding says propose-only, and it already did |
| B5 published-command gate corpus widening | **SHIPPED** — `platform/` added; surfaced 7 more one-disk files, all committed |
| B6 cache + empty-dir sweep | **DECLINED with the reason** — not a quiesce point |
| frozen evidence untouched | **VERIFIED** — 0 dirty lines on both directories |
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
| **(b) evidence NOT committed** | 14 `platform/` files cited by a published `python <path>`, **+7 more the widened gate then surfaced**; 111 mention-only; my own `_r3_*` probes | **21 + probes COMMITTED this round.** The 111 mention-only remain — basename mention is the weak signal and this lane has paid for use-vs-mention three times |
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

## B5 — the gate corpus now includes `platform/`, and it immediately found 7 more one-disk files

`platform/` sat **outside** the published-command gate's corpus
(`INCLUDE_PREFIXES = ("command-center/", "docs/")`). That is not incidental to B2 — it is the
mechanism. A committed report could publish `python platform/.../_probe_x.py` against a gitignored
file and no gate would ever notice. Measured with `_r3_widen.py`, which monkeypatches the
**shipped** module's prefixes and calls its own `scan()` rather than reimplementing the resolver
(5 controls, including strict-superset and a uuid target that must resolve UNRUNNABLE):

| | narrow corpus | widened |
|---|---|---|
| documents scanned, first measurement | 288 | 815 |
| NEW unrunnable surfaced | — | **19** |

**9 of those 19 were false positives**, all from
`platform/routing/fixtures/home/.agents/skills/**/SKILL.md` — a fixture HOME tree of third-party
skill docs used as *input* to the routing tests. Their `python scripts/foo.py` lines are relative to
a deployed skill's own home, not to this repo, so resolving them here is a category error. This is
the "third path root the resolver does not model" that INTEGRATE-R1 §4.2 predicted. Added to
`EXCLUDE_PREFIXES`, the same treatment `command-center/harvest/` already gets for verbatim dumps.

After that exclusion: corpus **290 → 321** documents, and **10** genuine NEW rows.

* **7 targets existed on disk** — bucket (b), the dangerous one, a clone could not run any of them.
  All 7 committed byte-unchanged.
* **1 target does not exist at all** — `platform/lib/ssot/verify.py`, cited by
  `platform/architecture/generated-ssot.md`. Not bucket (b); a published command naming a file
  nobody has. Carried as a **baseline row with an owner and a settling action**, because whether it
  was never written or was renamed is a judgement only the owning lane can make.

Gate now: **344 commands / 321 documents / 1 unrunnable (1 baselined) / 0 NEW / 0 stale**, rc 0,
self-test rc 0 including both marker controls.

### Two narrow exemptions, each controlled both ways

The 7 were gitignored by `platform/**/_probe_*.py` and `platform/**/_gen_*.py`, and 6 of 7 fail
`ruff format --check` (all 7 pass `ruff check`). Two exemptions were needed, and both are narrower
than the precedent they follow:

1. **`.gitignore` EXCEPTION 3** — negates exactly the 7 cited scripts, mirroring EXCEPTION 2's
   argument for `command-center/`. Control, both halves (`_r3_ignore_control.py`): of the **52**
   `platform/**/_probe_*.py` on disk, the 7 negated are visible **7/7**, and all **46** uncited
   siblings are **still ignored, 46/46**. A rule that had accidentally un-ignored the tree would
   look identical without that second half.
2. **`ruff.toml [format] exclude`** — format-only, for the 6. This is strictly narrower than the
   `extend-exclude` entry the repo uses for `command-center/_*.py`, because `ruff check` **stays
   live** on them. Control: the exclusion applies to *discovery*, so naming the files explicitly on
   the command line bypasses it — the check that matters is CI's own `ruff format --check .`, and
   in that mode the 6 are excluded while the same run still reports 59 other would-reformat files.
   A global disable would have reported 0.

The `[lint.per-file-ignores]` entry from B2 and this `[format]` block are deliberately different
mechanisms: one file has a lint error, six have format differences, and each gets the narrowest
tool for its own problem rather than one blunt exclusion for both.

### The baseline is now a real ratchet

Committing the 14 made both inherited rows **stale**, and the gate did what a ratchet should — it
went **red** and told me to delete them rather than letting the floor drift into slack. Deleted. The
floor went **2 → 0**, then back to **1** for the genuinely-missing target above, with an owner and a
settling action attached. Their `settling_action` had proposed deleting the unused binding at
`_p12_refute_predicate.py:107`; that was **not** done, because it edits another lane's evidence
bytes. The per-file ignore removes the reason instead of re-recording it.

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
