---
title: INTEGRATE-FINAL-2026-08-14
type: note
permalink: dqverify-repo-20261013/command-center/ssot/integrate-final-2026-08-14
---

# LANE SSOT — INTEGRATE (final stage), 2026-08-14

Measured in `C:/Users/Prekzursil/source/ast-integrate` @ `main`. Every number below was
produced by a command quoted here. Counts are SNAPSHOTS.

If any row still reads `UNKNOWN - not yet measured`, the unit died before measuring anything
and no verdict here may be cited. (None does.)

COVERAGE: §1–§6 measured. Disclosed and NOT measured, inline in §6: the content of the one
severed checkout git cannot read, the inventory's §5a table as a third numeric surface, and
whether the pre-existing `test_check_skill_dual_write` failure is green on Linux.

---

## 1. What was still unreachable when this stage began

INTEGRATE round 1 wired the rule's **text**: `ssot_wiring_check.py` with six codes W1–W6,
each red-proofed, invoked by a named CI step. That work is intact and I re-verified it.

What no wire held was the rule's **numbers**.

| surface | held by a wire before this stage? | measurement |
|---|---|---|
| the SSOT rule sentence | **yes** — W2 pins it to inventory §5 | `ssot_wiring_check.py` green, 21 tests |
| the drift gate is named and runnable | **yes** — W4/W5 | idem |
| CI runs the suite | **yes** — W6 + an explicit step | `.github/workflows/skill-dual-write.yml:114` |
| **the counts in the same block** — 178 / 168 / 9 / 168 / 1 / 132 / 5 / three | **NO** | nothing read them |
| **`population-classified.json` exists at all** | **NO** | W3 resolves only `.md` and `.py`, so the artifact the block calls "the machine-readable classification of all 178" was named by the rule and held by nothing |

This is the gap that matters, because the counts are what a future agent **acts on**. Whether
a checkout may be retired turns on "132 hold unpushed commits, dirty files or a staged index"
and "5 have no remote at all" — not on the rule sentence. And this lane has restated its
headline four times: **25 → 170 → 174 → 177 → 178**. Round 4's central defect was an
arithmetic that did not close (`9 + 168 = 177` against a population of 178) which every
reviewer read past, because nothing added it up.

Counting is an exact algorithm. Handing it to reviewer attention is how it was lost four
times; this stage hands it to code.

## 2. The wire: W7, added to a gate CI already runs

**No new CI step, and no edit to any workflow.** W7 rides an invocation that already exists
and is already pinned — which is why its reachability is inherited rather than newly claimed:

```
.github/workflows/skill-dual-write.yml:34   on: pull_request: branches: [main]
.github/workflows/skill-dual-write.yml:114  - name: gate-ssot-wiring self-test
                                              run: python -m pytest ci/tests/test_ssot_wiring.py -q
```

The suite's `test_the_real_repository_is_green()` calls `wiring.run(REPO_ROOT)` on the
checked-out tree, so W7 is evaluated against the real repo on every PR to `main`, not only
against fixtures. Two independent signals that the step is genuinely wired: W6 asserts it
from inside the checker, and `test_the_workflow_names_this_suite_explicitly` asserts it from
inside the suite. Both green.

**What W7 binds.** Twelve numbers across seven claim sentences, each compared to the field
that measures it:

| block claim | measured against |
|---|---|
| `**178 checkouts across 168 object stores**` | `population`, `distinct_object_stores` |
| `9 linked worktrees` · `168 independent clones` · `**1 severed worktree**` | `kind_arithmetic` terms |
| `9 + 168 + 1 = 178` | all four terms, and the sum |
| `**132 of them hold …; 5 have no remote at all.**` | `len(with_unique_or_uncommitted)`, `len(no_remote)` |
| `Three are named by live harness config` | `len(referenced_by_exec_config)` |

Plus the artifact against **itself**, first: `len(rows) == population`, `kind_arithmetic.closes`,
the terms summing to `on_disk`, and the severed list's length matching its arithmetic term.
Prose compared to a ruler whose own accounting does not close would be certified against a
broken instrument.

**Use-vs-mention, in the instrument.** The block deliberately PRESERVES refuted figures — 177,
25, 170 — inside `>` blockquotes so a dead end is not re-walked. A scanner over "every integer
in the block" would fire on that honesty. `_live_prose()` drops blockquote lines and each
claim is matched by its own anchored phrase: counting the field, not the document.

**Nothing forced an edit to `CLAUDE.md`.** All ten numbers already agreed with the artifact
when I measured them, so the gate landed green over unmodified prose. That also keeps this
change clear of the shared file that red-blocked PRs earlier in this program.

## 3. The end-to-end check, shown going red without the integration

`python command-center/ssot/w7_redproof.py`

```
  [OK ] positive-control        W7 silent=True  comparisons=12 (floor 12)
  [OK ] population-drift         fired=True exclusive=True codes=['W7-count-drift']
  [OK ] arithmetic-does-not-close fired=True exclusive=True codes=['W7-count-drift']
  [OK ] uncommitted-surface-drift fired=True exclusive=True codes=['W7-count-drift']
  [OK ] claim-sentence-deleted   fired=True exclusive=True codes=['W7-count-drift']
  [OK ] artifact-absent          fired=True exclusive=True codes=['W7-count-drift']
  [OK ] artifact-disagrees-with-itself fired=True exclusive=True codes=['W7-count-drift']
  [OK ] discrimination           pre-W7 gate exit=0 (SUCCESS:ssot-wiring-check wires=6 all intact) | W7 fires=True
SUCCESS:w7-redproof cases=8 all behaved
```

**The last line is the whole claim.** The same tree — population silently changed to 179 — is
handed to the checker as committed at `c72f71f5`, the pinned last commit before W7 landed,
reconstructed with `git show` and verified to lack the W7 code. That gate prints
`wires=6 all intact` and exits **0**. The new gate fires. State the two hypotheses first:
H1 "W7 detects count drift" against H2 "any checker goes red on a tree somebody edited" —
under H2 the old gate would fire too. It stays green, so the red is attributable to W7 and
not to the edit. A control that passes under both hypotheses is not a control.

`comparisons=12` is the other half. A checker that matched zero claims would print the same
`all intact` line; the positive control therefore fails CLOSED below a floor, so a regex that
quietly stops matching cannot masquerade as agreement. It is a COUNT of the thing being
compared — the estate's measured cure for a probe that reports parity because it is reading
one level above the collection it believes it is reading.

**And on the bytes CI actually checks out.** This working tree is CRLF; the Linux runner gets
the LF blob. `python command-center/ssot/w7_blobform.py`

```
  [OK ] blob-form control       files=8 CRLF=0 (expect 0)
  [OK ] gate on LF blobs        codes=[] (all wires intact)
  [OK ] inertness control       perturbed LF tree -> codes=['W7-count-drift']
SUCCESS:w7-blobform rev=HEAD LF-clean green-then-red
```

Data files come from `git show <rev>:<path>`, which returns the stored blob. `git archive` is
the one that applies EOL conversion and hands back CRLF on Windows — it is not used here.

## 4. Detector controls, and the two that caught ME

Nothing below is a silence I accepted.

- **Positive control** — W7 silent on the real tree AND ≥12 comparisons made.
- **Six treatments**, each firing W7 and **only** W7. Exclusivity is what makes it provable
  that W7 is the wire that noticed, rather than some collateral trip of W2/W3.
- **Fabricated control** in the DoD probe: `nonexistent-control-path` reads `exists=False`
  while five real checkouts read True, so the existence reader discriminates.
- **Wrong-collection control**: `len(rows) == population` asserted before any row is counted.

**Two of the repository's own controls fired on my incomplete work before CI could.** Both are
recorded rather than quietly fixed:

1. `test_every_invariant_has_a_red_proof` → `AssertionError: codes with no red-proof:
   ['W7-count-drift']`. The coverage gate mechanically refuses a code nobody has watched fire.
   It is why five paired mutations exist and not zero.
2. `test_the_scratch_copy_is_green_before_mutation` went red because
   `population-classified.json` was missing from `COPY_PATHS`, which cascaded into all six
   exclusivity assertions failing against a scratch copy that was already broken. That is the
   **third** round this same control has caught this same omission — the file's own comments
   record the first two.

**THE CONTROL INVALIDATED ITSELF ON LANDING — and I reproduced the lane's own round-1 bug.**
`w7_redproof.py` originally read the "pre-W7" checker from `HEAD`. It passed while W7 was
uncommitted, and the instant the integration commit landed the run turned into:

```
  [BAD] discrimination   pre-W7 gate exit=1 (FAILED:ssot-wiring-check cut=1) | W7 fires=True
FAILED:w7-redproof cases=8 not all behaved
```

HEAD had moved, so the control had silently become a copy of the treatment. This is exactly
what `_integrate_redproof.py` did in INTEGRATE round 1 — documented in that round's §4 — and
the next tool built in the same lane committed it again. Caught only because I re-ran the
proof *after* committing rather than trusting the pre-commit green.

Pinning is only half the fix: a pin can be re-pointed at a rev that DOES carry W7 and degrade
in silence again. So `_old_checker` now verifies the source it fetched genuinely lacks the W7
code and fails CLOSED. `python command-center/ssot/_probe_pin_failsclosed.py` proves the guard
is not inert, in both states:

```
CONTROL  c72f71f5 carries W7=False   HEAD carries W7=True
-- state A: pin = c72f71f5 (pre-W7) --  SUCCESS:w7-redproof cases=8 all behaved   --> exit=0
-- state B: pin = HEAD (carries W7)  --  [BAD] the control is a copy of the treatment --> exit=2
DISCRIMINATION: good-pin=0 bad-pin=2 -> guard fails closed
```

The first line is a control on the control: the two revs must genuinely differ in whether
they carry W7, or the probe would be comparing a state against itself.

**A detector failure of my own, kept rather than deleted.** `_probe_counts.py` first selected
"the first top-level list of dicts" and landed on `referenced_by_exec_config` (len 3), then
reported "distinct store values: 1" and "rows with unpushed/dirty/staged: 0". Both were
truthful readings of the **wrong collection** — one level above `rows` — which is the exact
shape that made `manifest["events"][ev]` report 3-and-3 on both sides earlier in this program.
The file now names `rows` explicitly and asserts its length against `population`.

**A wrapper's exit code is not a test result.** The backgrounded full-suite run reported
`exit code 0` while pytest reported `1 failed`: the `| tail -15` pipeline returned `tail`'s
status, not pytest's. Round 4 hit the same class through a different wrapper. The number in §5
is read from pytest's own summary line.

## 5. Gates, measured after the last edit

| gate | result |
|---|---|
| `python command-center/ssot/ssot_wiring_check.py` | `SUCCESS:ssot-wiring-check wires=7 all intact` |
| `python -m pytest ci/tests/test_ssot_wiring.py -q` | **`21 passed`** (16 before; +5 W7 mutations) |
| `python -m pytest ci/tests -q` | `1 failed, 866 passed, 1 skipped in 53.25s` — see below |
| `python command-center/ssot/w7_redproof.py` | `SUCCESS:w7-redproof cases=8 all behaved` (re-run AFTER the commit, against the pinned pre-W7 control) |
| `python command-center/ssot/_probe_pin_failsclosed.py` | `SUCCESS:pin-failsclosed a re-pointed pin is refused, not silently accepted` |
| `python command-center/ssot/w7_blobform.py` | `SUCCESS:w7-blobform rev=HEAD LF-clean green-then-red` |
| `uvx ruff@0.15.17 check` (touched files) | `All checks passed!` |
| `uvx ruff@0.15.17 format --check command-center/ssot/ ci/tests/test_ssot_wiring.py` | `51 files already formatted` |

**The one failure is not mine**, on two independent signals:
`test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`
dies on `os.fsdecode(b"\xff")` → `UnicodeDecodeError`. (a) `git status --porcelain` over my
scope shows I did not touch that file. (b) It is a Windows platform difference in another
lane's suite, and round 4 measured the identical failure at the blob level before my change
existed. **NOT-CHECKED:** whether it passes on the Linux runner — I cannot run that here.

## 6. Definition of Done — re-scored independently, not inherited

Scored by `python command-center/ssot/_probe_dod.py`, which reads the artifact and counts
rows. It does not read any round's prose verdict.

| DoD item | status |
|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS, scoped.** 178/178 carry a kind — `{own-store: 168, worktree: 9, severed-worktree: 1}` — of which **177 by two agreeing signals** and 1 by a third signal validated in both states. `signals_agree` stays False on that row and is not overwritten |
| unique-content measured per clone | **PASS, scoped — and narrower than previously written.** `dirty_files`/`staged_files` are measured on **177 of 178**; `unpushed_commits` on **173 of 178**. The unmeasured rows are named, not rounded away: the 5 without `unpushed` are the no-remote checkouts (no upstream to diff), settled at blob level in round 3 — **zero unique committed bytes**; the 1 without `dirty`/`staged` is the severed worktree, where every git command exits 128. See residual 1 |
| inbound-reference measured per clone | **PASS.** 178 rows scanned; exactly **3** carry `inbound_exec`, matching `len(referenced_by_exec_config) = 3` — `Documents/Playground`, `source/agent-skills-toolchain`, `source/ast-harness-reconcile`. Scheduled Tasks, PATH and env each measured with a synthetic-row control that discriminates, all silent |
| a one-sentence SSOT rule written | **PASS, and now enforced in both halves.** The sentence is pinned by W2; its **numbers** are pinned by W7, red-proofed 6 ways and shown blind in the pre-W7 gate |
| nothing deleted | **PASS.** No clone, worktree or evidence directory touched. Five named source checkouts still present with a fabricated control reading False. No `worktree` subcommand run anywhere. `CLAUDE.md`, `docs/ssot/`, every workflow and `ruff.toml` are untouched by this stage |

## 7. Residuals — what is NOT done

1. **One checkout in the population has NO content measurement at all.** The severed worktree
   `~/.codex/plugins/cache/agent-skills-toolchain/plugin-install-64I3il/agent-skills-toolchain/0.2.0`
   returns `None` for `dirty_files`, `staged_files` and `unpushed_commits`, because its `.git`
   file names an admin dir that no longer exists and every git command inside it exits 128.
   It is classified, and its content is unknown. **UNVERIFIED [uncertain 20–55%]** that it
   holds nothing unique. **Settling experiment:** walk it with the filesystem rather than git
   and hash each file against the canonical store — the same blob census round 3 used for the
   five no-remote checkouts. Do NOT reach for `git worktree repair` to make git answer: from
   the plugin cache it rewrites links bidirectionally and would repoint the real trees at the
   cache.

2. **W7 pins CLAUDE.md only. The inventory's §5a table is a third numeric surface and is NOT
   bound.** Measured consistent today (`178`, `168`, `9 + 168 + 1 = 178`, `132`, `5` at
   `docs/ssot/SSOT-CLONE-INVENTORY.md:479-488`). It was left unbound deliberately: the
   inventory carries a §0 HISTORY table whose rows legitimately record superseded
   measurements, so a pattern general enough to catch drift there would fire on correct
   content — a gate that false-fires on honesty is worse than no gate. **Settling
   experiment:** bind only the §5a table by parsing rows under that heading, and prove it
   stays silent when §0's historical rows are left untouched.

3. **W7 pins phrasing, by construction.** A benign reword of a claim sentence turns CI red
   with `the sentence carrying '<label>' is gone from the block`. That is deliberate — a
   deleted number must not be quieter than a wrong one — but it means a future round that
   rewrites the paragraph must update `COUNT_CLAIMS` in the same change. Stated so nobody
   reads that red as a false alarm.

4. **The gate runs on `pull_request` only.** `skill-dual-write.yml` has no `push` trigger, so
   a direct push to `main` bypasses W7 exactly as it bypasses W1–W6. Inherited from the wire
   this stage rode, not introduced by it. **Settling experiment:** add `push: branches:
   [main]`, which is a one-line edit to a shared workflow and so belongs to whoever owns that
   file, not to this lane.

5. **Nothing retired and nothing deleted, still correct.** 43 retire candidates stand
   identified. Two checkouts hold files that exist nowhere else, one only in a staged index
   that `git worktree remove` destroys — and that command follows junctions and deletes their
   targets. Prefer moving a directory aside.

6. **`~/source/_advver_M14/scratch` remains the sharpest exposure**, unchanged: 0 commits, no
   remote, thousands of untracked entries in no store anywhere. Not this stage's to fix, and a
   uniqueness census of a tree under active write cannot license any action.

7. **Two sibling receipts left dirty and uncommitted** — `drift-gate.json` and
   `salvage-atrisk.json`. Both were already modified before this stage began; landing
   `salvage-atrisk.json` would overwrite the salvage evidence with a post-salvage re-run.
   Neither is mine to land, and my commit used an explicit pathspec so neither was swept in.

8. **Every count is a snapshot.** `main` moved during this program. Re-run before acting.

9. **Not pushed.** Local `main` is ahead of `origin/main`; pushing was not in scope.