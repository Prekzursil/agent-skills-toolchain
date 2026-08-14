# SLOP — BUILD lane, round 5

Round 4 was audited and came back **PARTIAL** with two CONFIRMED defects and two overclaims.
This round fixes exactly those and does not re-litigate what passed. Every number is anchored to
the rev it was measured at — the worktree moved under this lane again (`a946b643` → `5423de0f`),
as it has every round.

**Headline: fixing the audit's D1 turned up a defect the audit did not have.** Re-running the
bucket-(c) cycle on a *real* bucket-(c) candidate — instead of round 4's tracked stand-in —
showed the file regenerates perfectly on this disk while **four of its producer's six inputs are
untracked**. Nobody who clones this repo could rebuild it. Round 4's bucket-(c) test asked only
*"does a producer script exist?"*; the test that matters is *"are the producer's INPUTS tracked?"*
One of the three bucket-(c) rows fails it and is now bucket (b) — a file that would have been
deleted as "reproducible scratch" and could not have been reproduced.

---

## What the audit found, and what happened to it

| # | audit finding | kind | this round |
|---|---|---|---|
| D1 | the executed deletion targeted `_r4_shellcov.out.json`, ALREADY TRACKED at the classification rev, so it is in **no** bucket — "one deletion EXECUTED" read as a bucket-(c) deletion | overclaim | **FIXED + went further.** R4's sentences annotated REFUTED in place (original wording kept); cycle re-run on a real bucket-(c) candidate, which the run then **reclassified out of bucket (c)** |
| D2 | DoD-4 evidence used pathspec `.../probes/*/control`, which matches **0 tracked files** as a git pathspec — inert control | broken detector | **FIXED.** Refutation measured, not asserted (glob 0 vs real path 2); replaced by hash identity + a live-detector control + a both-states check |
| O1 | "all 5 `pytest` targets located on disk and ALL ARE TRACKED" — the probe's own receipt prints `"NOWHERE": 1` | overclaim | **SENTENCE FIXED** in R4 with the correctly-scoped version and the settling experiment named |
| O2 | "23 format + 11 lint" is stale and an UNDERSTATEMENT (audit measured 51/14) | stale number | **RE-MEASURED at `5423de0f`: 52 format / 13 lint findings across 9 files, 0 tracked** — and turned into an actionable per-lane split |

---

## DoD status

| DoD item | verdict | evidence |
|---|---|---|
| 1. every candidate classified into four buckets with evidence | **PASS** | `_r5_reclassify.out.json` @ `5423de0f`: 305 rows == 305 untracked, `partition_total: true`, classifier's own 5 controls PASS, histogram b=179 / c=3 / d-census=100 / d-zero=18 (…and 1 of the 3 c-rows reclassified, below) |
| 2. bucket (b) committed rather than deleted | **PARTIAL — unchanged as a gap, but no longer un-costed** | dangerous subset still empty by construction; 179 weak-signal files still belong to other lanes. New: **66 of the 99 bucket-(b) `.py` are ruff-clean today and cost the gate nothing to commit**; 33 need their owner to format first, listed per lane |
| 3. bucket (c) deletions each backed by a shown regenerating command | **PASS** | **0 bucket-(c) files deleted**, so no deletion lacks backing. The command is now SHOWN and EXECUTED on a real bucket-(c) candidate (`_r5_bucket_c.out.json`, rc 0, `K8_restored: true`) |
| 4. frozen-evidence directories untouched | **PASS, and this time proven** | `_r5_frozen.out.json` → `FROZEN-UNTOUCHED-PROVEN`: 9/9 files byte-identical to their HEAD blobs, fail-closed counts 7 + 2, live-detector control fires at 5 lines, both-states comparator check |

---

## F1 — D2: the frozen-evidence control was inert. Measured, then replaced.

The refutation is not quoted from the audit, it is re-derived (`_r5_frozen.py`, rc 0):

```
tracked files under command-center/p2-wave/probes/*/control      -> 0
tracked files under command-center/p2-wave/probes/AUD-0006/control -> 2
```

Round 4 read the left number as *clean*. It means *matched nothing*. A control that passes
identically under both hypotheses is not a control — it proves the instrument ran.

Five signals now, each able to fail:

| signal | reading @ `5423de0f` |
|---|---|
| R0 refutation holds (glob 0, real path > 0) | `true` |
| C1 fail-closed counts | `casualty/probes` **7**, `AUD-0006/control` **2** |
| C2 live detector — adjacent dirty parent vs frozen child, same instrument, same instant | control `command-center/casualty` = **5 dirty lines**, both frozen dirs = **0** |
| C3 byte identity vs HEAD blob, all files | **9/9 same** |
| C4 both-states on the comparator (exact blob bytes MATCH, bytes+1 DIFFER) | `true` / `true` |
| C5 no new untracked file inside either frozen dir | `[]`, `[]` |

C2 is what makes the zeros mean something: a 0 next to another 0 is a silence, a 0 next to a 5
from the same command at the same moment is a reading. C4 is what makes C3 mean something —
"all 9 hashes matched" is exactly what a constant-returning comparator would also print. No
frozen file was opened for write; the C4 mutation happens on bytes in memory.

## F2 — D1: the cycle re-run on a real bucket-(c) file, and what it exposed

```
target   platform/architecture/_secfirst_selfaudit.out.json   (untracked, bucket c)
producer platform/architecture/_secfirst_selfaudit.py         (TRACKED)
command  python platform/architecture/_secfirst_selfaudit.py
```

`python command-center/slop-report/_r5_bucket_c.py` → rc 0, `SUCCESS:r5-bucket-c`:

| control | reading |
|---|---|
| K1 producer tracked | `true` |
| K2 target really ABSENT between delete and regenerate | `true` |
| K3 command rc | `0` |
| K4 nothing OTHER than the target changed (full `-uall` porcelain diff) | `true`, `K4_other_lines: []` |
| K5 byte identical | `false` — `0e4f836d…` → `371ee887…` (a receipt embeds the rev it was taken at) |
| K6 substance reproduced (same 61 checks, same controls, same auditor-valid) | `true`, 61 → 61 |
| **K7 clone-regenerable** | **`false`** |
| K8 restore verified by digest | `true` |

**The cycle ends in a restore, and that is not a dodge.** The target is another lane's receipt,
and regenerating a receipt is not idempotent — this one re-derives working-tree counts that have
moved since its pin, so re-running it *overwrites a measurement taken at a different rev*. Backing
the bytes up outside the repo, proving the property, then restoring byte-for-byte removes the
objection round 4 declined on, without destroying anything. **Deleted by this lane: 0.**

### K7 is the finding

"Reproducible" has two meanings and no previous round separated them:

* (i) regenerable **in this worktree** by a tracked command — round 4's test;
* (ii) regenerable **by anyone who clones the repo** — the only one that makes deletion safe.

`_secfirst_selfaudit.py` is tracked, exits 0, and rebuilds its output faithfully. Four of its six
declared inputs are not:

```
platform/architecture/_secfirst_measure.out.json            UNTRACKED
platform/architecture/_secfirst_measure2.out.json           UNTRACKED
platform/architecture/_secfirst_measure3.out.json           UNTRACKED
platform/architecture/_secfirst_probe_denydefault.out.json  UNTRACKED
platform/architecture/security-first.md                     tracked
command-center/WORK-UNIT-CATALOG.json                       tracked
```

Applied to every bucket-(c) row (`_r5_reclassify.py`, extractor controls E1/E2/E3 all pass):

| bucket-(c) row | producer tracked | untracked inputs | verdict |
|---|---|---|---|
| `command-center/p2-wave/_i3_blobfmt.out.json` | yes | 0 of 8 | **BUCKET-C-CONFIRMED** |
| `platform/architecture/_secfirst_probe_denydefault.out.json` | yes | 0 of 2 | **BUCKET-C-CONFIRMED** |
| `platform/architecture/_secfirst_selfaudit.out.json` | yes | **4 of 12** | **RECLASSIFY TO (b)** |

So bucket (c) at `5423de0f` is **2 files, not 3**, and bucket (b) is **180, not 179**.

**Scope of the K7 test, inline: it is ONE LEVEL, not transitive.** A file whose only untracked
input were itself bucket (c) could still be regenerable through a chain. That escape hatch does
not save this row — three of its four untracked inputs (`_secfirst_measure{,2,3}.out.json`) are
not bucket-(c) rows at all, so no chain reaches them. Settling experiment for the general case:
close the input graph transitively and re-run; UNVERIFIED for any future row until then.

## F3 — O2: the ruff cost, re-measured, and DoD-2 made actionable

Three numbers exist for the same quantity because the tree moves: round 3's **23 format / 11
lint**, the audit's **51 / 14**, and this round's **52 format / 13 lint findings across 9 files**
at `5423de0f`. None of them is wrong; a number quoted without its rev is.

| split | format | lint |
|---|---|---|
| tracked (what CI actually checks out) | **0** | **0** |
| untracked | 52 | 9 files / 13 findings |
| …of which bucket (b) | 29 | 7 |
| …of which bucket (d) | 22 | 2 |

`gate-lint-format` is therefore green on tracked content at this rev, and every red byte is in a
file CI has never seen. That is the whole DoD-2 tension in one line: committing evidence is what
would turn it red.

**The actionable half nobody had measured** — of the 99 bucket-(b) `.py` files,
**66 are ruff-clean at the CI pin and cost the gate nothing to commit**; 33 need their owner to
format first:

| lane | clean (commit today, zero gate cost) | red (owner formats first) |
|---|---|---|
| `platform/lib` | 34 | 5 |
| `platform/architecture` | 13 | 4 |
| `command-center/_adv0031` | 11 | 0 |
| `platform/council` | 3 | 0 |
| `command-center/{hook-audit, mcp-audit}` | 2 | 2 |
| `platform/{corpus, routing}` | 1 | 1 |
| `docs/` (probe scripts at depth 1) | 2 | 16 |
| `command-center/grounding` | 0 | 3 |
| `command-center/p2-next` | 0 | 2 |
| **total** | **66** | **33** |

Grouping is by the first two path segments, so `docs/<file>.py` groups as itself; the `docs/` row
above is the hand-aggregate of those 18 rows and the machine table in `_r5_cost.out.json` shows
them individually. This lane still does **not** sweep them: they are other lanes' in-flight
evidence and outside `command-center/slop-report/**`. The recommendation is now specific —
each owning lane commits its own clean 66 immediately, and formats the 33 before committing.

## F4 — one deletion executed, and it is mine

`_r5_peek.py`, my own orientation script, superseded by `_r5_reclassify.py` within the round.
Bucket (d) by this lane's own standard, with the reference detector controlled in both states:

* `_r5_peek` → **1 occurrence**, in `_r5_buckets_snapshot.json` — a **census output whose job is
  enumerating every untracked path**. Use-vs-mention: a machine listing is not a dependency.
  (Round 4 was caught by this exact shape when a census script read as a "producer".)
* control `check_published_commands` → **80 occurrences across 39 files**. The scanner is live.

Deleted, `Test-Path` after → `False`. Nothing else was deleted by this lane.

---

## Detector controls, all of them

| probe | control | reading |
|---|---|---|
| `_r5_frozen.py` | R0 refutation measured; C1 fail-closed on zero; **C2 adjacent dirty parent must report > 0 while frozen reports 0**; C4 both-states on the comparator | 0 vs 2 · 7 + 2 · 5 vs 0 · match + differ |
| `_r5_bucket_c.py` | K2 absent-between (else the cycle proves only that a file exists); K4 over the FULL `-uall` porcelain so a new untracked side-effect is caught; K8 restore verified by digest | all `true` |
| `_r5_reclassify.py` | E1 **known answer** — the extractor must independently find the 4 inputs derived by hand; E2 a known-tracked literal reads tracked; E3 a fresh uuid4 literal reads untracked AND absent | `E1_missing: []` · `true` · `true` |
| `_r5_cost.py` | X1 clean temp file reads clean; X2 mis-formatted temp file reads red on BOTH format and lint; X3 tracked oracle positive + uuid4 negative. Controls live **inside** the repo so `ruff.toml` applies | all `true` |
| reused | `_r4_buckets.py`'s own C1–C5 (mention positive 30 / negative 0, producer ±, gate agreement) | `PASS: true` |

### My own detector failed once this round, and it is recorded

`_r5_cost.py` v1 printed `lint_rc: 1` with `"Found 13 errors."` **and** `lint_files_n: 0`. A
single run reporting two things that cannot both be true is a **detector failure, not a finding**.
Cause: ruff 0.15's default `check` output is a rustc-style diagnostic whose path sits on a ` --> `
continuation line, so a parser keying on "line starts with a path" found nothing. Fixed by reading
`--output-format=json`, plus a permanent `lint_parser_consistent` guard that refuses to publish a
number when rc and parsed-findings disagree. Had I published v1's output, "0 lint files" would
have read as a clean tree.

---

## What this round did NOT touch

* Did not sweep, format, or commit any file outside `command-center/slop-report/**`.
* Did not delete any bucket-(c) file (2 confirmed candidates belong to other lanes — proposed).
* Did not re-litigate R0 (`git clean -Xdf` still banned), R11 (`skills/` ↔ `.agents/skills/`
  sanctioned), R12 (`_advver_M14` is outside this repo), or the `NUL` writer (settled in round 4).
* Did not run `sync-from-live.ps1`, `sync-skills.ps1 -Prune`, or the harness installer.

## Residual, stated rather than folded into a pass

* **DoD-2 remains PARTIAL.** 180 weak-signal bucket-(b) files are still uncommitted. They are
  other lanes' evidence and out of scope; the round's contribution is the costed, per-lane list
  that makes committing them a decision rather than a shrug.
* **UNRESOLVED, disclosed:** the first cost run (broken parser) reported 58 would-reformat with
  **2 tracked**; the two runs after it reported 55 then 52 with **0 tracked**. The −3 from run 2
  to run 3 is exactly my own three files being formatted. The run-1 → run-2 delta (−3, and
  tracked 2 → 0) is **not** explained by the parser fix and cannot be recovered — run 1's file
  list was overwritten by run 2. Most likely a sibling's working-tree change in that window.
  Settling experiment: run the probe twice back to back and diff the file lists; if they differ
  with no commit between, the shared worktree is moving under the instrument.
* **K7 is one-level, not transitive** (scoped inline in F2, with why it does not change this
  verdict).
* **NOT-CHECKED:** the ~84 non-ruff `quality.yml` steps, unchanged from rounds 2–4. Nothing here
  claims main is green — only that `gate-lint-format` is green on tracked content at `5423de0f`.
* **UNVERIFIED (unchanged rounds 2–5):** whether any committed receipt digest-locks carried probe
  bytes. This is still why no evidence file is reformatted.

---

## Post-commit verification (`f725baf4`)

Everything below was run AFTER the commit, against committed bytes — not against the working
tree that produced them.

| check | reading |
|---|---|
| commit surface | 11 paths, 1 `M` + 10 `A`, **0** under `--diff-filter=D`, **0** paths outside `command-center/slop-report/` |
| published-commands gate at HEAD | rc **0** — 377 commands across 335 documents, **0 NEW**, 0 stale (1 inherited baseline row still open) |
| gate self-test | rc **0**, including both example-marker controls |
| **blob-level ruff at my commit** (`_r2_gate_now.py --rev f725baf4`) | `ruff check rc=0`, `format --check rc=0`, **0 would-reformat**, `all_controls_pass: true` |
| frozen evidence at lane END | `FROZEN-UNTOUCHED-PROVEN` again — 9/9 hash-identical, live-detector control fires at 5 |

The ruff line is the CI-relevant one: it reads the **stored blobs** (LF), not the CRLF worktree,
so a local green cannot disagree with CI the way this estate has already been bitten by once.
Before the commit the pre-commit self-check predicted exactly one unresolved command
(`_r5_bucket_c.py`, untracked at the time, with the control firing on both documents); after the
commit the real gate reports 0 NEW. Predicted and observed agree.

### A side effect I caused, disclosed rather than quietly reverted

Re-running `_r2_gate_now.py` to produce the blob-level line above **overwrote
`_r2_gate_now.out.json`, which was already dirty at lane start** (it is one of the four
`_r2_`/`_r3_` receipts the round-4 handoff recorded as dirty-before-that-round too). Whatever
uncommitted reading it held is gone and cannot be recovered. Mitigating facts, not excuses: it is
this lane's own instrument, its content is a rev-stamped ruff measurement whose own banner says
*"THIS TREE MOVES — re-run before citing this line"*, and the producer is tracked and takes
`--rev`, so any rev can be re-measured on demand. I restored the file to its committed state with
`git checkout --` so it now sits in a well-defined, reproducible state rather than one I invented.
The other three pre-existing dirty receipts were never opened by this round and are left exactly
as found.

---

*Round-5 artifacts, all committed: `SLOP-BUILD-R5.md`, `_r5_frozen.py`, `_r5_bucket_c.py`,
`_r5_reclassify.py`, `_r5_cost.py` and their `.out.json`, plus `_r5_buckets_snapshot.json`.
Corrections annotated in place in `SLOP-BUILD-R4.md` — the refuted wording is struck through and
kept, never deleted.*
