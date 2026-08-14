# Lane CIGREEN — round-3 corrections

An independent verifier reviewed this lane's round-1 report and returned PARTIAL: one real
factual defect and four numeric overclaims. This file is the durable retraction. Every number
below was re-measured by me in round 3 rather than copied from the verifier — a reviewer's
finding is a single signal too. The earlier wording is quoted, not deleted, so the dead end is
retired rather than re-walked.

Re-measure everything here with `python command-center/ci/interpreter_floor_gate.py --report`
for the pin inventory, and with `git ls-tree` / `git cat-file` for the blob-level claims.

---

## D1 — CONFIRMED DEFECT. Retracted.

**Refuted wording (round 1):** *"the declared file scope was `.github/workflows/**` and
`command-center/ci/**`. `command-center/ci/` DOES NOT EXIST."*

**Measured** (`git ls-tree -r --name-only <rev> command-center/ci/`):

| revision | tracked under `command-center/ci/` |
|---|---|
| `ae8205a4` (brief baseline) | 0 |
| `27da3215` (round-1 spawn HEAD) | 1 — `command-center/ci/orchestrator-flake-note.md` |
| `dfea977d` (round-1 fix commit) | 1 |
| `28d42732` (round-1 PR commit) | 1 |
| `c9f6cca4` (this lane's floor gate) | 2 |
| `8e7ff68c` (this file's own commit) | 3 |

> The last row read `| HEAD | 1 |` until round 4. **REFUTED there, kept here:** `HEAD` names
> whichever revision a reader happens to be holding, and it was already 3 when this file's own
> commit landed. That is O3's defect — a number with no anchor — committed inside the section
> that names it. Every row above is now a fixed sha.

Added by `e4b72cfe`, 2026-08-12 23:25, *"docs: record the gate-sast download flake before the
re-run erases it"*. The directory existed at every revision this lane actually touched. It is
absent from exactly one revision — `ae8205a4` — the brief baseline the same report had already
proven 92 commits stale.

**Correct wording:** *`command-center/ci/` exists and is tracked, holding one 2,968-byte
markdown flake-note. There was no CI code in it, so it could not host the round-1 fix, and
those changes landed in `command-center/mcp-audit/**` and two skills paths instead.*

**Why it mattered:** that sentence was the justification for working outside declared file
scope. The scope decision was right; the justification was fabricated from a revision already
known to be wrong, with no second probe. The failure was recall, not detection — one
`git ls-files` at HEAD would have settled it.

---

## O1 — both the original number and the verifier's correction were truncated.

**Refuted wording:** *"skill-dual-write had run 12x, all success."*
**Verifier's correction:** *"200 runs returned, 192 success / 8 failure"* — itself capped, its
`--limit` was 200.

**Measured** (`gh run list --workflow skill-dual-write.yml --limit 400`): 290 runs returned,
below the cap so not truncated — **261 success / 22 failure / 7 cancelled**, spanning
2026-07-21 to 2026-08-14.

The load-bearing conclusion is untouched: the brief's claim that `gate-cs-wiring` and
`gate-skill-deploy-hop` had *never executed* is false — they were already green in run
`31667122476`, steps 7 and 8.

## O2 — the numbers came from the CRLF working tree; the conclusion survives.

**Refuted wording:** *"Byte count unchanged 12,330 … both roots sha256 216b26de6f38."*

| revision | blob oid | LF bytes | LF sha256 | CRLF bytes | CRLF sha256 |
|---|---|---|---|---|---|
| `28d42732^` | `8f5d75c561b7` | 12080 | `b8ac7a518b70` | 12330 | `1d24ccfba36b` |
| `28d42732` | `de37c839ee46` | 12080 | `ee3d69237eed` | 12330 | `216b26de6f38` |

`12,330 / 216b26de` is the CRLF working-tree form of the post-fix blob. Both underlying claims
hold when measured on the stored blob: the byte count really is unchanged (12,080 -> 12,080),
and both skill roots really are byte-identical (same blob oid at both revisions). Flagged
because this repo's own rule is to measure the stored blob, and the report used the surface it
warns against.

## O3 — the count was right at its revision; the sentence lacked the anchor.

**Refuted wording:** *"9 of 11 python-version pins are 3.11."*

| revision | total pins | 3.11 | 3.12 |
|---|---|---|---|
| `27da3215` (round-1 spawn HEAD) | 11 | 9 | 2 |
| `dfea977d` (round-1 fix commit) | 11 | 9 | 2 |
| `HEAD` | 13 | 11 | 2 |

The surface grew after the lane exited: `rule-audit.yml` was added by `4ef63930` and
`hook-audit.yml` by `7ccaa24b`; `git merge-base --is-ancestor <add-commit> dfea977d` returns
rc 1 for both, so neither existed at the measured revision. The verifier's 10-of-12 was correct
at its own measurement time, between those two commits.

**Conceded, and it is the real defect:** an unpinned count in a durable report goes stale
silently, and a reader cannot tell a wrong number from an old one. The fix is the revision
anchor, not a different number. `interpreter_floor_gate.py --report` now recomputes this
inventory on every run for the same reason.

## O4 — the count was right; the unit was never named.

**Refuted wording:** *"Fixed 3 f-string-backslash sites across 2 files."*

Measured by walking the AST of the blobs at `27da3215` for a backslash inside an f-string
`FormattedValue`: `_r4_cr_settle.py` has **3 expressions across 2 f-string statements** (lines
105 and 118); `_r4_selfcheck.py` has **1 expression in 1 statement** (line 54).

**Correct wording:** *4 backslash-bearing f-string expressions across 3 statements in 2 files.*
"Sites" named no unit, which is why the same fix could be reported as 3 and as 4 in one report.

## O5 — same reality, ambiguous denominator.

**Refuted wording:** *"15/15 steps, 0 skipped"* (run `31712123884`).

Measured: the `gate-skill-dual-write` job reports **18 steps, all success, 0 skipped** —
numbered 1-15 plus 29 `Post Run setup-python`, 30 `Post Run checkout`, 31 `Complete job`.
The three first-ever executions are confirmed present and green: step 9 `gate-ssot-wiring
self-test`, steps 10 and 11 `gate-skill-description-ratchet`.

---

## What round 3 shipped instead of re-litigating

`interpreter_floor_gate.py`, in this directory. Round 1 filed the split interpreter surface as
residual #3 with a prototype that lived only in scratch. It has since produced a **second**
live CI red (`Path.read_text(newline=)`, a 3.13 keyword, on a 3.11 pin), so the class is now
measured twice rather than argued once.

Sweep at the discovered 3.11 floor, **4 that do not parse**. Since round 4 the gate prints
the revision it measured, so its own count is quotable instead of rotting:

```
scanned 2643 tracked .py at the 3.11 floor @ 64c28c70db98+2dirty -> 4 that do not parse
```

| file | line | error |
|---|---|---|
| `skills/codex-databricks-fanout/scripts/batch_runner.py` | 18 | `from __future__` not at the beginning |
| `.agents/skills/codex-databricks-fanout/scripts/batch_runner.py` | 18 | same |
| `command-center/ssot/salvaged-from-scratch/aud_crlf.py` | 30 | f-string expression cannot include a backslash |
| `command-center/ssot/salvaged-from-scratch/v10_spot.py` | 32 | f-string expression cannot include a backslash |

That output reconciles with three findings made independently of it, which is the reason to
believe the detector: the two `batch_runner.py` rows are the defect PR #282 fixes and are still
live because that PR is deliberately unmerged; the two `salvaged-from-scratch` rows are round-1
residual #1, which the verifier also re-measured as still broken; and `_i4_wire_ci.py`, the
third residual, has correctly **dropped off** the list because sibling `46903c7e` fixed it.

Neither remaining pair is this lane's to fix. `salvaged-from-scratch/` is provenance-named
content owned by an active sibling lane, and editing recovered bytes is how salvage evidence
gets destroyed — the same reasoning that scopes the ruff and opengrep exclusions around
`command-center/casualty/probes/` rather than editing the files inside it.

The gate is **not wired into CI**. Wiring means editing `.github/workflows/`, the shared file
this repo's ground rules name as the single hazard that red-blocked every PR, and the sweep is
currently red on pre-existing breakage. Landing a detector and turning it into a merge blocker
are separate decisions, and the second one is the owner's.

---

# Round 4 — what an independent verifier confirmed against round 3

The verifier re-measured by executing rather than reading. Verdict PARTIAL: all three DoD items
passed on re-execution, **one sentence was REFUTED**, and this file shipped **two numbers that
were already stale when it landed**. Both are corrected in place above with the old wording
quoted, not deleted. Everything below was re-measured here — a verifier's finding is a single
signal too.

## R4-1 — REFUTED: the commit credited with fixing the coverage gate

**Refuted wording** (round 1, carried unexamined into round 3): *"Task 1's premise was already
fixed by sibling `14202f88`."*

**Correct wording:** *the `gate-tests-coverage command-center` step was already green at
`28aa4cb4`, which landed 6h16m earlier and is a strict ancestor of `14202f88`.*

Three mechanically independent signals, all naming `28aa4cb4`:

| signal | measurement | result |
|---|---|---|
| CI step conclusion | last red / first green, Actions API | red at `97f5eb06` (run `31651795259`), green at `28aa4cb4` (run `31652895009`) |
| git content history | `git log -S 721c4e577ca5 -- command-center/WORK-UNIT-CATALOG.json` | exactly one commit: `28aa4cb4` |
| ancestry | `git merge-base --is-ancestor`, both directions | `28aa4cb4`→`14202f88` rc 0; reverse rc 1 |

Only two commits sit in `97f5eb06..28aa4cb4`, and only `28aa4cb4` touches either side of the
REACH-6 comparison (`WORK-UNIT-CATALOG.json`, `sources/REGISTER.md`). `14202f88` is real work —
*"REACH-6 could be switched off by deleting one field"* — but it hardens a check that was
already passing, and a later commit cannot turn an earlier commit's run green.

**Control limitation, disclosed:** the textbook form — parent RED, child GREEN — is unavailable.
`28aa4cb4^` (`23ee1622`) has **no** `quality` run at all, because pushes here are batched and
Actions runs the tip. The bracket above is the substitute and it is weaker by exactly that much:
it pins the flip to a two-commit window, then eliminates one of them by file surface, rather
than observing the flip itself.

**Worth keeping:** the run at `28aa4cb4` concluded **failure** while this job and this step were
both **success**. A run conclusion answers "did anything in the workflow fail", never "did my
gate pass"; reading it as the latter is how a green step gets reported as red.

## R4-2 — the two stale numbers are the same defect twice

| location | shipped | measured in round 4 | fix |
|---|---|---|---|
| D1 table, last row | `HEAD` = 1 | 3 at `8e7ff68c`, this file's own commit | rows pinned to shas |
| sweep paragraph | 2,618 tracked `.py` | 2,619 at `c9f6cca4` **and** at `8e7ff68c` | count now printed with its revision |

2,618 was never true at any commit: the sweep ran before `git add` staged the gate itself, so it
counted a tree that was never committed. Both are O3's own defect — an unanchored number cannot
be told apart from a stale one — committed inside the retraction that names it.

## R4-3 — the structural fix, and the control that proves it fires

Correcting two digits does not stop the third. The gate now reports what it scanned:

```
scanned 2643 tracked .py at the 3.11 floor @ 64c28c70db98+2dirty -> 4 that do not parse
```

The anchor is mutation-tested, not asserted. Baseline `--self-test` is 8/8 green; three stubs of
`describe_tree` each turn it red, each caught by a *different* check:

| mutation | rc | caught by |
|---|---|---|
| baseline, unmutated | 0 | — |
| returns `("UNKNOWN", 0)` | 1 | commit-id shape **and** the dirty read |
| real-looking sha, always `1` | 1 | the clean read |
| real-looking sha, always `0` | 1 | the dirty read |

The control is hermetic — a throwaway repo, read clean then dirty — because reading *this*
worktree would race the siblings committing into it. Not theoretical: `HEAD` moved twice during
this round, `a71a7c0a` → `e91cee80` → `64c28c70`, and the tracked `.py` count went 2,641 → 2,643
between two of my own readings.

## R4-4 — PR #282's premise, contested and settled

`ruff.toml` has excluded both `batch_runner.py` mirrors since `451248bb` (2026-07-24) on the
grounds that it is a Databricks notebook export where "the cell structure puts `from __future__`
after widget setup … valid there and invalid as standalone Python". That is a direct challenge
to the open PR, written three weeks before it.

Measured on the committed blob at `HEAD`: the file carries the `# Databricks notebook source`
header, **0** `# COMMAND ----------` separators and **0** `# MAGIC` lines. `# COMMAND` *is* the
cell boundary in that format, so with none present the file is one cell and one compile unit —
which is why it returns rc 1 on 3.11, 3.12 and 3.14 alike. The exclusion's account of *why* the
file looks like this is right; its conclusion that the placement is therefore valid does not
survive the missing separators.

UNVERIFIED [likely, 55-80%]: that a Databricks cell compiles exactly as CPython does here. I
measured the separators and CPython's behaviour, not the Databricks runtime. Settling
experiment: run the notebook in a workspace, or insert one `# COMMAND ----------` above the
`from __future__` line and see whether the import is then accepted. Until then PR #282 stays
open and unmerged, which is where the owner wanted it.
