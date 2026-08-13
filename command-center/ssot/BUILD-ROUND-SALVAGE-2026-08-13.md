# LANE SSOT — BUILD lane, salvage + enumeration round

Measured 2026-08-13 in `C:/Users/Prekzursil/source/ast-integrate` @ `main`. Every number below
was produced by a command named beside it. Counts are SNAPSHOTS.

COVERAGE: S1, S2, S3, S3b measured and shipped. **S4 (the corrected full-disk checkout total)
DID NOT COMPLETE** — the sweep outran the round. Its section carries `UNKNOWN` and no number
from it may be cited; the ≥27 floor comes from S3/S3b, which did complete.

Baseline at start: HEAD `27da3215`, `origin/main` `27da3215` (0 ahead / 0 behind), 265 dirty.

---

## S0. What this round did NOT do, because it was already done

The lane's Definition of Done was closed by earlier rounds and I re-checked rather than
re-ran it. Do not rebuild these:

| prior work | state | evidence |
|---|---|---|
| the 25-checkout inventory, SSOT rule, retire criterion | committed | `docs/ssot/SSOT-CLONE-INVENTORY.md`, 1 of 1 tracked |
| 24 measurement scripts + receipts | committed | `git ls-files command-center/ssot/` = 89 |
| drift gate + CI wiring + red-proof | committed | `INTEGRATE-2026-08-13.md`, `ci/tests/test_ssot_wiring.py` |

`git status --porcelain -- docs/ssot command-center/ssot` was **empty** at start, so the
grounding's "highest urgency: the artifacts are untracked" was already stale. The two items
those rounds ranked #1 and #2 and explicitly did **not** do were the salvage. That is this
round.

## S1. The 5 at-risk files are real, and both my first probes said they were not

`docs/ssot/SSOT-CLONE-INVENTORY.md` §4 named two checkouts holding content existing nowhere
else. Still true when measured:

| source | kind | files | bytes |
|---|---|---|---|
| `D:/wt-salvage-probe` | staged index, never committed | 2 | 24,345 |
| `_b5-toolchain` (`80130e1`) | 1 unpushed commit, independent clone | 3 | 58,230 |

**Two detector failures of my own, both pointing the DANGEROUS way** (reporting safety where
there is exposure). Recorded in `salvage_atrisk.py`'s docstring rather than edited away:

1. **`git cat-file -e` as the uniqueness test → `unique=0`.** `D:/wt-salvage-probe` is a
   **linked worktree of the canonical store**, so `git add` wrote its blobs into the *shared*
   object database. Measured: `exists_in_store=True, reachable_from_any_ref=False`. The file
   is present in canonical and simultaneously one `git gc --prune` from deletion, because the
   only thing pointing at it is an index that `git worktree remove` destroys. Existence and
   reachability are different questions and an existence probe answers them identically — it
   cannot separate *H1 preserved in history* from *H2 loose object about to be collected*, so
   it is not a control for this claim. Replaced with membership in
   `git rev-list --objects --all`, the set gc preserves.
2. **`git log --format=%H --not --remotes` with no positive ref → "0 unpushed files".** It
   does not default to `HEAD` once `--not` is present; it returns **empty**. That was a clean
   bill of health for a checkout holding the only copy of three files. Fixed by passing `HEAD`
   explicitly; the probe now prints the query's return code so silence cannot pass as an answer.

Corrected reading — **5 of 5 unreachable**, matching the inventory exactly:

```
CONTROL: canonical reachable objects=21400  known-reachable=True  fabricated=False -> discriminates
[wt-salvage-probe]  AT-RISK  exists=True   reachable=False  ci/tests/test_codex_profiles.py
[wt-salvage-probe]  AT-RISK  exists=True   reachable=False  tools/monitorcore/r0_monitor_live_gate.py
[b5-toolchain]      AT-RISK  exists=False  reachable=False  tools/mcp-manager/core/health.py
[b5-toolchain]      AT-RISK  exists=False  reachable=False  tools/mcp-manager/mcp_health.py
[b5-toolchain]      AT-RISK  exists=False  reachable=False  tools/mcp-manager/tests/test_health.py
```

The `exists` column is the whole lesson: `True` for one source and `False` for the other,
while `reachable` is `False` for both. An existence probe would have called half of them safe.

## S2. Salvage — SHIPPED, commit `6c7e99f2`

82,575 B now in tracked history. Integrity is the point, so it is measured twice: each blob's
SHA recorded at read time, recomputed from the written file, and recomputed again from the
**staged** blob after `git add`.

| stage | result |
|---|---|
| written copy vs source blob | **5 of 5 identical** |
| re-checked after `ruff format` ran over sibling files | **5 of 5 identical** |
| **staged blob** vs source blob | **5 of 5 identical** |

That third row matters because `git add` printed *"LF will be replaced by CRLF the next time
Git touches it"*. The warning is about the working-copy checkout, not the stored object; the
staged blobs are byte-identical, which is the level CI reads and git preserves.

**Sources untouched** — blobs read with `git cat-file blob`, never checked out. Verified after:
`D:/wt-salvage-probe` still stages the same 2 paths, `_b5-toolchain` still has `80130e1` and a
clean working tree. **Nothing was deleted; no checkout was retired.**

**Preserving bytes is not endorsing code, and not a restore.** The files are parked under
`command-center/ssot/salvaged-at-risk/<source>/<original path>` rather than at their real
paths. The b5 commit is a **superseded parallel implementation**: main ships a dead-MCP
detector via `core/claude_adapter.py` + `core/models.py` (PR #196), b5 ships
`health.py` + `mcp_health.py`. Both sides have 42 files in `tools/mcp-manager/` — which reads
as parity and is a 3-for-3 swap. Salvaging makes that decision *possible later*; it does not
make it. **UNVERIFIED [inline]:** none of the five was executed, imported or tested here.
Settling experiment: run b5's `test_health.py` against main's implementation.

**SHARED FILE DECLARED — `ruff.toml`.** One `extend-exclude` entry added for
`command-center/ssot/salvaged-at-risk/**`, following the precedent that file already sets for
`salvaged-from-scratch` ("evidence, not source, so the bytes win"). Both states measured: with
it the format gate is green; **without it 2 of the 5 would be reformatted**, destroying the
byte-identity that is the whole point. `ruff check` passes either way. This is an append to a
list, the lowest-conflict shape of edit to a shared file, but it is a shared file and is named
here for that reason.

**A hook false positive, disclosed.** The TDD-guard PreToolUse hook flagged
`salvaged-at-risk/.../test_health.py` for `[skip added]: @pytest.mark.skipif(`. It is not a
weakened test: the file is frozen evidence copied byte-identically out of a stranded commit and
was never edited. The hook reads a staged diff and cannot distinguish "I weakened a test" from
"I preserved someone else's file verbatim" — the same use-vs-mention shape this lane keeps
hitting. Not suppressed, just recorded.

## S3. The inventory's enumeration has a NAME-vs-IDENTITY defect — PROVEN

`NO-REMOTE-REPO-TRIAGE.md` noticed two working copies of this repo absent from the 25-checkout
table and flagged the enumeration as worth a follow-up. Root cause, read from
`sweep_all_checkouts.py`:

```python
if TARGET not in origin.lower() and TARGET not in common.lower(): continue
```

A checkout counts only if the literal string `agent-skills-toolchain` appears in its remote URL
or object-store path. That is a test for the repo's **name in a path**, standing in for a test
of what the repo **is** — the same use-vs-mention shape as above, one level up. It is blind to
a clone with no remote, a `git init`-only working copy, and any renamed directory. The walk
reached both missed dirs (depth 3, inside `MAXDEPTH=7`); the identity test rejected them.

`enum_defect_proof.py` — four cases chosen so each failure mode is visible, and the detector
must answer both ways in both directions:

```
case                              OLD(name)  history  content  NEW   expected
canonical                         True       True     True     True  OLD-FIRES
chk (1 commit, no remote)         False      False    True     True  OLD-MISSES
scratch (0 commits, no remote)    False      False    True     True  OLD-MISSES
ToolUniverse-secfix (unrelated)   False      False    False    False BOTH-MISS
```

All 7 assertions PASS, including the two that keep the result honest: **OLD fires on
canonical** (so the old test is not simply broken, it is specifically name-bound) and **NEW
does not fire on an unrelated repo** (so the replacement is not vacuous).

Two findings inside that table:

- **`scratch` is findable by NO other signal.** 0 commits means the history signal cannot see
  it; only reading bytes can. Any enumeration built on refs or remotes will miss it forever.
- **`chk` reports `history=False` despite having a commit.** It is a `git init` + snapshot, not
  a clone — it does not share canonical's root commit. So *both* missed checkouts are
  content-identified, and a history-only fix would have caught neither.

**A third detector failure, caught by its own control.** The content signal hashes working-tree
bytes and compares against the object store. First run:

```
CONTROL: reachable=21474 positive=False negative=False -> discriminates=False
FAILED:enumerate content signal does not discriminate
```

The **positive** control failed: canonical's own `AGENTS.md` did not match canonical's own
reachable set, because the working tree is CRLF and git stores LF (`windows-shell.md` §8b).
Uncontrolled, the content signal would have returned `False` for every repo on this box —
silently re-creating the exact blind spot it was written to close, since `scratch` is findable
by nothing else. Fixed by hashing both raw and LF-normalised bytes. **This is the third time in
this round a tool reproduced the defect class it was built to catch.**

## S3b. The two missed checkouts, classified on every DoD axis

So the enumeration finding does not leave two known checkouts unclassified.
`classify_missed.py`, using the same two independent worktree-vs-clone signals the inventory
used, each first shown to discriminate on a checkout of known kind:

```
CONTROL known linked worktree    dotgit=FILE  common=outside   expected=worktree
CONTROL known main checkout      dotgit=DIR   common=inside    expected=main-checkout
control discriminates FILE vs DIR: True
```

| checkout | kind (A / B, agree) | commits | origin | dirty `-uall` | staged | inbound refs |
|---|---|---|---|---|---|---|
| `~/source/_advver_M14/chk` | **independent clone** (DIR / inside, agree) | 1 | none | 0 | 0 | **0** |
| `~/source/_advver_M14/scratch` | **independent clone** (DIR / inside, agree) | **0** | none | **7,803** | 0 | **0** |

Both signals agree on both, so neither row is a detector artifact.

`scratch` is the worst shape on this box: **0 commits and 7,803 uncommitted entries** — nothing
in it is in git anywhere, so its entire contents are one `rm -rf` from gone, with no remote and
no history to recover from. That is what the prior round's near-miss was about, and it is why
its retire-safe verdict was withdrawn. Unique content for both was already measured by
`NO-REMOTE-REPO-TRIAGE.md` (7 unique files, all deliberately-retired ChatGPT-web orchestrator
code) plus the 21 live files already snapshotted into `salvaged-from-scratch/`.

Neither is referenced by anything — consistent with the inventory's finding that 23 of 25
checkouts are referenced by nothing.

## S4. Full-disk re-enumeration — DID NOT COMPLETE IN THIS ROUND

`enumerate_checkouts.py` re-sweeps `C:/Users/Prekzursil` and `D:/` applying all three signals
and diffs against `all25.json`. It exceeded a 900 s foreground budget, was moved to a
background run per AGENTS.md §4a, and **still had not finished its filesystem walk when this
round ended.** Its control passed (`reachable=21531 positive=True negative=False`), so the
CRLF fix is confirmed working; the walk is simply expensive (`full-sweep.json` records 911 git
checkouts, and `D:/` at depth 7 is the cost).

**Corrected total: UNKNOWN — not measured. Do not cite a number from this round.**

What IS established without it, and is safe to cite:

- The inventory's **25 is a floor, not a count** (S3, proven both-states).
- **At least 27** checkouts exist; the 2 beyond the table are classified in S3b.
- The classification of the original 25 is **unaffected** — the defect is in *which* checkouts
  get enumerated, not in how an enumerated one is classified.

Cost work done so this is cheap next time rather than repeated: `classify()` is now
spawn-frugal (the NAME and CONTENT signals read `.git/config` and file bytes directly, 0
spawns; only a repo that neither decided pays one `cat-file`), and the walk now persists to
`walk-paths.json`, because `full-sweep.json` recorded *"911 scanned"* and discarded the paths —
so the expensive half could not be reused and had to be re-walked from scratch.

### S4a. A FOURTH detector failure — my own walk count is 59% junction aliases

The walk finished and reported **4,447** `.git` locations against the prior round's 911. That
5x jump is not the box growing; it is my walk counting the same directories twice. The tell was
in its own distribution:

```
  2553  C:/Users/Prekzursil/Local Settings/Application Data
   835  C:/Users/Prekzursil/Local Settings/Temp
    50  C:/Users/Prekzursil/Documents/GitHub
    50  C:/Users/Prekzursil/My Documents/GitHub      <- the same 50, second alias
```

`Local Settings` and `My Documents` are legacy Windows compatibility **junctions** onto
`AppData/Local` and `Documents`. `SKIP` excludes `AppData` *by name*, so the walk refuses the
real path and then walks straight into it through the alias. **`Documents/GitHub` and
`My Documents/GitHub` at exactly 50 each** is the estate's own §3c tell: a suspiciously equal
pair is a collection-level mistake far more often than a real quantity.

`dedupe_walk.py` resolves every path with `os.path.realpath` and collapses aliases, offline
against `walk-paths.json` — no re-walk. Its control has to discriminate before the number
counts: a known alias pair must resolve equal *and* a genuinely distinct pair must not.

```
CONTROL: 'Documents' == 'My Documents' -> True; 'Documents' == 'source' -> False; discriminates=True
raw walk entries      : 4447
distinct real paths   : 1840
junction duplicates   : 2607
```

**So 4,447 is not a count of anything and must not be cited.** The honest figure for `.git`
locations is **1,840 distinct**. This also means any "belongs" total from that run needs the
same realpath collapse before it is trusted — a single physical checkout reachable through a
junction would otherwise be counted twice, inflating the very number this section exists to
correct. That is why S4's total is still reported as UNKNOWN rather than as 4,447-derived.

The generalisable rule, which is the durable part: **on Windows, a `SKIP` list keyed on
directory NAMES does not exclude a directory — it excludes one route to it.** Junctions give
the same bytes a second name, and `AppData` has had exactly such an alias since Vista.

## S5. Definition of Done

| DoD item | status | evidence |
|---|---|---|
| every clone classified worktree-vs-clone by measurement | **PASS for 27, with a disclosed floor** | inventory §1 for the 25 (two independent signals) + S3b for the 2 it missed (same two signals, controls shown to discriminate). S3 proves the enumerator is name-bound, so 27 is a floor — but every checkout *known* to exist is now classified |
| unique-content measured per clone | **PASS** | inventory §2/§2b; S1 re-measures the 2 at-risk checkouts on the corrected reachability test; S3b for the 2 missed (via `NO-REMOTE-REPO-TRIAGE.md`) |
| inbound-reference measured per clone | **PASS** | inventory §3 — 8 field-level refs, 23 of 25 referenced by nothing (not re-run; best-evidenced part of the prior art); S3b measures 0 for the 2 missed |
| a one-sentence SSOT rule written | **PASS** | inventory §5, mirrored into the repo-root `CLAUDE.md` `<!-- SSOT-WIRE -->` block, CI-gated |
| nothing deleted | **PASS** | read-only against every source; writes confined to `command-center/ssot/**` plus the declared `ruff.toml` line |

## S6. Residual — what is NOT done

1. **S4's corrected total is unmeasured** — the sweep did not finish inside this round. The
   floor of ≥27 is safe to cite; a specific number is not. **Settling experiment:** re-run
   `python command-center/ssot/enumerate_checkouts.py` under `longrun` with a multi-hour
   budget; it is now spawn-frugal and persists `walk-paths.json`, so a later run can skip the
   walk entirely.
2. **The enumeration fix is a script, not a repair of the inventory table.** `all25.json` and
   the inventory's §1 table still say 25, and `docs/ssot/SSOT-CLONE-INVENTORY.md` is NOT edited
   by this round. I deliberately did not rewrite the table on a partial sweep: replacing a
   known-low number with an unverified one is worse than a disclosed floor. The repo-root
   `CLAUDE.md` SSOT block also still says 25 and is CI-gated against the inventory
   (`ssot_wiring_check.py`), so the two must be corrected **together** or the gate goes red —
   which is the gate working, not a bug.
3. **`enumerate_checkouts.py` has never been run to completion**, so its end-to-end output is
   UNVERIFIED [uncertain, 20-55%] beyond the control and the classify path, both of which were
   exercised. `enum_defect_proof.py` — which shares the signal logic — did run to completion
   with all 7 assertions passing, so the *signals* are proven even though the *sweep* is not.
4. **The mcpctl DIVERGED set is still open** (inventory §4, 5 files, `safety.py` +17 scratch-only
   / +11 main-only). Unchanged by this round. **Settling experiment:** run the scratch
   `test_safety.py` against main's `safety.py` and see which assertions fail.
5. **The `mcp-manager` port decision is still open** and is judgement, not a differ — see S2.
6. **Nothing retired.** The precondition stands: retire nothing until its work is on a pushed
   branch. This round removes the *data-loss* exposure for 5 files; a copy in an evidence
   directory is not the same as the work being landed where it belongs, so it does not by
   itself license retiring either checkout.
7. **Local `main` is ahead of `origin/main` and not pushed** — pushing was not in scope.
8. **`git worktree remove` follows junctions and deletes their targets** (measured 2026-08-10,
   destructive, NOT re-verified here). Never run a `worktree` subcommand from the Codex plugin
   cache: `git worktree repair` rewrites links *bidirectionally*, so running it there would
   repoint the real live worktrees at the cache.
