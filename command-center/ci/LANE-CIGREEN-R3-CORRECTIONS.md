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
| `HEAD` | 1 |

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

Sweep at the discovered 3.11 floor, 2,618 tracked `.py`, **4 that do not parse**:

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
