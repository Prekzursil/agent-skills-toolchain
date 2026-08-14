# HOOKRESEARCH — BUILD lane, round 2

Round 1 of this build lane shipped `hook_predeploy_gate.py` and settled P0/P1/P3-premise. Its §9
left five items. This round works that list, and opens with something none of the five predicted.

**If sections still read `UNKNOWN - not yet measured`, the unit died before measuring them and no
verdict there may be cited.**

COVERAGE: §1 and §2 are measured and committed. §3-§5 carry their own state below.

---

## 1. Unplanned and urgent: CI's format gate was RED on main, and the blob gate could not see it

Not on any round's list, found while checking whether my own new files would pass CI.
`ruff format --check .` — one of the two commands `gate-lint-format` runs — fails on
`command-center/hook-audit/_g5_vendorcaps.py`, committed unformatted by `bac65640` (round 1 of
this lane). Its own follow-up `c2ab418f` reformatted the files its author knew about and missed
this one. Round 1 §6.7 records that near-miss as *caught*; one file survived it.

**Why nothing caught it is the more useful half.** `_r4_blobgate.py` does the hard part
correctly — staged blobs, the committed `ruff.toml`, both-states controls — but walks a
**hardcoded eight-entry `PATHS` list**. A file committed outside that list is not *clean* to it,
it is **invisible**. That is the same shape as `check_citations`' own H4 hole, where a number
carrying no `cite:` marker was not unbacked but unseen. The blob gate reported GREEN throughout.

`_b9_format_tracked.py` replaces the hand-maintained list with a **derived** one: every tracked
`*.py` plus every tracked ruff config, materialised from the index with a single
`git cat-file --batch` and checked with the pinned ruff. Blobs, not the worktree — a Windows tree
is CRLF, git stores LF, CI checks out LF (windows-shell §8b).

Both states, same invocation:
<!-- cite: id=R2-fmt-after file=B9-FORMAT-TRACKED.json path=tracked_unformatted_count value=0 -->
<!-- cite: id=R2-fmt-files file=B9-FORMAT-TRACKED.json path=controls.C3_files value=2595 -->
<!-- cite: id=R2-fmt-c4 file=B9-FORMAT-TRACKED.json path=controls.C4_config_parity value=True -->
<!-- cite: id=R2-fmt-before file=B9-CRLF-SPLIT.json path=genuinely_unformatted.0 value=command-center/hook-audit/_g5_vendorcaps.py -->

| state | offenders | files measured |
|---|---|---|
| before the fix | 1 (`_g5_vendorcaps.py`) | 2,593 |
| after `ruff format` | **0** | 2,595 |

Shipped in `2a139b87`.

### 1b. My own probe reported 5 offenders and 4 of them were innocent

Recorded, not quietly fixed, because the shape is this program's most repeated failure. The
first version materialised only `*.py` + the **root** `ruff.toml`, so
`tools/mcp/patent-search-mcp/{patent_api,server,tests/*}.py` were formatted against settings
that do not govern them — ruff resolves config from the nearest `pyproject.toml` upward, and
that file was not in the temp tree.

**Controls C1, C2 and C3 all PASSED while this was true.** None of them can separate *genuinely
unformatted* from *formatted against the wrong config*; a control that cannot distinguish the
two hypotheses only proves the instrument ran. **C4 (config parity, fail-closed)** is the one
that separates them — 16/16 configs present — and with it the probe re-reports 1 offender,
agreeing with the worktree measurement it had contradicted.

What sent me back to the instrument was a **self-contradiction**, not suspicion:
`_b9_crlf_split.py` measured every blob as LF, 0 CRLF, including all four suspects — so a file
cannot be clean under CRLF and dirty under byte-identical LF. That refuted the CRLF hypothesis
and left no story in which the five were all real.

## 2. Item 4 — `check_citations.py` in CI

UNKNOWN - not yet measured

## 3. Item 2 — per-edit-check's secret gate

UNKNOWN - not yet measured

## 4. Item 3 — the `SessionEnd` settings hazard

UNKNOWN - not yet measured

## 5. Item 5 — behavioural equivalence for the 12 DIVERGED bodies

UNKNOWN - not yet measured

## DoD status

Round 1 met all four; this round does not re-claim them. Its own contribution per item:

| DoD item | verdict |
|---|---|
| every wired hook timed against its budget | PASS (prior art, rounds 1-4). Not re-measured here and not claimed as mine. |
| inert hooks proven inert by a fired probe | PASS (prior art). |
| /rollback producer gap resolved or a deploy plan written | PASS (round 1: plan + a failing axis-P gate). |
| false-positive sources named with a fix | UNKNOWN - not yet measured for this round's additions |
