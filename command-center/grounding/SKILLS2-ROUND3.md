---
title: SKILLS2-ROUND3
type: note
permalink: dqverify-repo-20261013/command-center/grounding/skills2-round3
---

# LANE SKILLS2 — ROUND 3

STATUS: **MEASURED.** Every row names the probe that produced it and the control that proves
the probe can fail. Raw stdout is committed beside this file.

## P0 — what round 3 could NOT obtain, stated first

The re-entry brief says *"a verifier CONFIRMED defects last round. Fix those."* **I never
received that list**, and I am not going to invent one.

- The `PRIOR ROUNDS` JSON handed to this unit is **truncated mid-round-1-audit** — it ends inside
  that audit's `reproduction` field on the characters `"C`. Round 2's build and audit are absent
  from it entirely.
- No round-2 audit report exists on disk. Measured, not assumed:
  `git status --porcelain -uall | grep -iE "s2|skill"` returns only round-**1** audit/verify
  artifacts (`_audit_s2_*`, `_verify_s2_*`, all timestamped 00:17–04:05), and a repo-wide grep for
  `SKILLS2|S2-R2` returns 11 files, none of them an audit.
- The round-2 verifier **did** run: it re-executed four of this lane's probes, leaving
  `S2-R2-BOUNDARY.json`, `S2-BUDGET-REFIT.json`, `S2-NEGCASE.json` and `S2-RENDER-PROBE.json`
  modified in the working tree. Its *conclusions* went to the orchestrator and did not reach me.

So round 3 could not fix a list. It **re-derived independently** — and found four defects, three
of them in this lane's own committed work. The status of the actual round-2 findings is
**NOT-CHECKED**, and nothing below should be read as "the verifier's items are closed".

COVERAGE — what round 3 did **not** measure:
- Why the render budget `B` moves between sessions (still UNVERIFIED; sample 4 cannot help — see R3-A).
- The per-description truncation cap value (round-1 residual, still UNVERIFIED).
- `~/.agents/skills` was **read-only** all round. R3-C ran on a temp COPY; the real vault was never written.
- No new negative-case clauses were authored (see "What round 3 deliberately did not do").

---

## The work list

| # | item | kind | outcome |
|---|---|---|---|
| R3-A | 4th independent sample of the render boundary | new evidence | **DONE** — mechanism corroborated; sample 4 does **not** discriminate H-CONST vs H-SESSION and says so |
| R3-B | the fleet char total is measured with a parser the renderer disagrees with | **defect in this lane's instrument** | **FIXED (sentence + probe)** — overcount is **440**, not 7,253 |
| R3-C | round 2's vault handback carried an **unexecuted prediction** | untested claim | **EXECUTED** — prediction CONFIRMED on a copy, with a negative control |
| R3-D | item 2's remedy "a targeted merge of those six files" | **untested assumption** | **REFUTED for 1 of 6** — `critique.mjs` would be destroyed by a copy |
| R3-E | round 2's census control anchored to `HEAD` and called it "frozen" | **defect in a committed control** | **FIXED (one line) + both-states proof** |
| R3-F | 7 SKILL.md frontmatters are not valid YAML; 1 description is silently halved | new defect, reported | **REPORTED, not edited** — priced, handed to the owner |

---

## R3-B — the number every char claim in this lane rests on was measured wrong

`_s2_r3_sample4.py`, `_s2_r3_yamldiag.py`, `_s2_r3_loaderparse.py`.

Rounds 1–3 all measured description length with **one hand-rolled frontmatter reader**. Round 2
even caught a *different* parser blind spot (folded scalars, −8,843) and treated the survivor as
correct. Round 3 introduced a **mechanically independent** second parser — PyYAML 6.0.3, a
separately-authored C implementation — and the two disagree by **7,253 chars**.

Only 3 descriptions differed non-trivially, so a 7,253-char gap is **self-contradicting = a
detector question, not a finding.** Attribution (the C2 control is *attribution*, not a
tolerance — every char must land on a named file or nothing may be cited):

| bucket | files | chars |
|---|---:|---:|
| PyYAML **rejects** the frontmatter (`ScannerError`) | 7 | 6,766 |
| folded-scalar **re-spacing** (no text lost) | 4 | 487 |
| **total** | 11 | **7,253 = the measured gap exactly** |

Then the decisive question: **which parser does the renderer agree with?** The injected skill
listing is an external signal this lane does not produce. Hypotheses stated first; they predict
different observable text.

- **`bc-drive-plus`**: on disk 793 chars. PyYAML stops at **353**. The rendered listing stops at
  the *same words* — `…(closes bc-drive's` — and the next characters on disk are ` #1 open gap)`.
  A ` #` opens a YAML comment. **440 chars (55%) of that skill's trigger surface never render.**
- `sora`, `prompt-optimizer`, `frontend-a11y`: rendered text ends at the strict cut too, but the
  hand-rolled text has **no content after it** — these are whitespace re-spacing, not loss.
- `agent-as-judge` (PyYAML-**rejected**) renders **in full**: the loader is lenient about the
  `": "` PyYAML throws on.

> **ROUND-3 CORRECTION.** *My first truncation predicate was wrong and is recorded, not deleted:*
> `runs_past = h.endswith(tail) and len(h) > len(y)` returned **MIXED / INCONCLUSIVE**, because a
> folded scalar PyYAML re-spaces is *shorter while ending at the same words* — length alone cannot
> separate truncation from re-spacing. Corrected predicate: the rendered tail appears in the
> hand-rolled text with **non-whitespace content after it**. Verdict then: `H-STRICT`, 1 real
> truncation, 3 re-spacings.

**Consequence, and it is a correction to items 1 and 4, not a new claim:** the loader-faithful
fleet total is **115,021**, not the **115,461** rounds 2–3 cite — an overcount of **440**. Every
absolute char figure in this lane (fleet total, the fitted `B`, the "~7,300 over", "net −17
chars") inherits a **±440 (0.38%)** systematic error. **Sensitivity test: the verdict is stable.**
Re-fitting sample 4 with loader-faithful lengths gives `B=102,600` at **the same 2 mismatches /
328** (hand-rolled: `B=103,050`, 2 mismatches). The mechanism is untouched; only the decimals move.

## R3-A — sample 4, and what it honestly does not prove

`_s2_r3_sample4.py`. All five controls pass: C1 premise (0 absent, 0 empty) · C2 attribution
(above) · C3 order (first bare `ui-drive` rank 294/328, last is the last entry on disk, **0** bare
before the zone) · C4 decoys · C5 split.

| observed set handed to the fitter | best mismatches |
|---|---|
| **true sample-4 set** | **2** |
| 200 random 30-subsets (seeded, deterministic) | min 27 · median 30 |
| alphabetically first 30 | 30 |
| the 30 longest descriptions | 29 |

**Q1, the new thing this sample can settle: is sample 3 a transcription error?** Symmetric
difference between sample 3 and sample 4 is **empty** — 30/30 names, and the same 4 in-zone
survivors (`ui-ux-pro-max` 353, `using-superpowers` 159, `video-watermark-removal` 1154,
`workflow-authoring` 1062). `H-TRANS-OK`. The load-bearing hand transcription behind R7 is
reproducible by an independent reader.

**Q2, stated before the probe ran and not walked back: sample 4 does NOT discriminate H-CONST
from H-SESSION.** It is a lane subagent spawned by the same orchestrator with a near-identical
preamble to sample 3, so both hypotheses predict the same boundary. Reporting it as a fourth
independent vote for `H-SESSION` would be exactly the overclaim this lane keeps making.
**H-SESSION still rests on samples 1 vs 2/3, unchanged.**

**H-PARSE is refuted a fourth way, on evidence nobody had.** The brief named "a frontmatter key
the parser rejects" as a live competing hypothesis; round 1 tested extra *keys*
(`metadata`/`license`/`origin`) and never tested **YAML well-formedness**. Now measured: **7**
files carry frontmatter a strict YAML parser rejects outright, and **6 of the 7 render their
descriptions in full**. If a parse failure suppressed a description those six would be first to go
dark. The seventh, `workflow-foundry`, is bare — but it sits at rank ≥307, inside the truncation
zone, so its bareness is **confounded** and is not evidence either way. C5 also reproduces the
cross-namespace split **5/6** (byte-identical description text, `DESC` in one namespace and `BARE`
in the other, same session) — a file's own bytes cannot render two ways at once.

## R3-C — the handback prediction, executed

`_s2_r3_vault.py`. Round 2 correctly re-scoped "no new drift" and handed the vault back with a
prediction: *copy the description lines into `~/.agents/skills` and `needs_merge` must return to
397.* **A prediction in a handback is a claim, not a receipt.** Round 3 ran it — through the real
`deploy-skills-daily.plan()` classifier, on a temp COPY of the 7 skill directories.
**`C:/Users/Prekzursil/.agents/skills` was never written; the guard census below re-confirms it.**

| state | summary | needs_merge | SKILL.md refused |
|---|---|---:|---|
| A — vault copy as it is today | DIVERGED 7 | 7 | all 7 |
| B — after the minimal handback action | IDENTICAL 6 / DIVERGED 1 | **1** | `tdd-workflow` only |

**6 reconciled. `H-CLOSES` — the handback instruction is complete and correct.**
Repo-vs-vault differing lines: exactly **1** for six of the seven skills.

Two controls: the both-states verdicts **differ** (identical counts would make the probe inert),
and `tdd-workflow` — which differs by **4** lines and was already DIVERGED *before* round 1 — is a
built-in **negative control** that must NOT reconcile. It did not.

> **ROUND-3 CORRECTION, my own.** The first version copied the whole `SKILL.md` and printed
> *"only 7 of 6 reconciled"* — a self-contradicting number, so a detector fault, not a finding. A
> whole-file copy also reconciles `tdd-workflow`, which is not part of the +6 and destroys the
> negative control. Rewritten to perform the *minimal* action the handback actually specifies.

## R3-D — item 2's proposed remedy would have destroyed live work

Item 2 says closing the vault no-op "needs a targeted merge of those six files, not the deploy
hop". **That sentence assumes the six are one-way behind the repo. Nobody measured the
direction** — even though round 2 measured exactly that for the *seventh* file and found the
opposite of what two earlier reports assumed.

Set arithmetic alone cannot answer it: a one-line **replacement** yields 1 unique line on each
side and reads as "two-way". The question the owner needs answered is *would a copy destroy
anything*, so vault-only lines are classified — a line that is the old main-guard the repo
deliberately replaced is not work at risk.

| file | repo-only | vault-only | **substantive** vault-only | copy safe? |
|---|---:|---:|---:|---|
| `axe_scan.mjs` · `capture.mjs` · `layout_lint.mjs` · `run_audit.mjs` · `visual_diff.mjs` | 11 each | 1 each | **0** | yes |
| **`critique.mjs`** | 281 | 19 | **18** | **NO — union merge** |
| `dead_button_crawl.mjs` (differ control) | 8 | 69 | 69 | NO — union merge |

**5 of 6 are safe to copy; `critique.mjs` is a THIRD two-way-diverged file** (after
`workflow-authoring` and `dead_button_crawl.mjs`) holding 18 lines of live-only work — a
Claude-facing critique-input/rubric path the repo copy does not have. Handing the owner "copy the
six" would have destroyed it.
Differ control: `dead_button_crawl.mjs`, independently measured two-way by round 2, is reported
destructive here; reconstruction checked in **both** directions on every file.

## R3-E — a committed control that had quietly stopped working

Round 2 wrote that its census control was *"anchored to the frozen R1 git blob, not to disk"*,
precisely because an earlier version died when its own defect was repaired. **That sentence is
REFUTED.** The code reads `git_desc("HEAD", n)` and calls the result "the frozen R1 blob". `HEAD`
is not frozen — it resolved to `1e9cfe81` only because round 2 had not committed yet.

Measured at round-3 `HEAD` (four commits later), **before** any change:

```
H1 OLD-is-inert-here (True/True) while NEW discriminates (True/False): False
CONTROL: NOT DISCRIMINATING -- do not cite the numbers below
```

The control was comparing the *fixed* state against itself. One-line fix — pin `R1_REV` to the
immutable SHA `1e9cfe81`. Both-states proof, same command, same file:

| state | H1 | control |
|---|---|---|
| before (anchor = `HEAD`) | False | **NOT DISCRIMINATING** |
| after (anchor = `1e9cfe81`) | True | **DISCRIMINATING** |

With the control live again, round 2's census claim **reproduces**: `transcribe` PRE `True` → R1
`False` → R2 `True`; net vs pre-round-1 **OLD +0 / NEW +0**; 0 skills currently missing a WHEN.
So round 2's *number* was right and its *control* was dead — the number is now re-earned.

## R3-F — two defects found, deliberately not edited

1. **`bc-drive-plus` loses 440 of 793 description chars (55%)** to a ` #` that opens a YAML
   comment (`#1 open gap`). Confirmed by two independent signals: PyYAML cuts there, and the
   rendered listing ends at the same words.
2. **7 SKILL.md frontmatters are not valid YAML** — `agent-as-judge`, `cv-studio`,
   `diff-blind-test-synth`, `execution-grounded-bon`, `refactor-equivalence`, `rubric-verifier`,
   `workflow-foundry` — all `ScannerError: mapping values are not allowed here`, an unquoted plain
   scalar containing `": "`. **Latent, not live:** no repo tool YAML-parses `SKILL.md` (measured —
   the `yaml.safe_load` importers are in `hooks/per-edit-check`, `tools/mcp`, `tools/search-expansion`
   and `scripts/merges`, none of which read skills), and the renderer is lenient. It breaks the
   day any consumer uses a strict parser.

**Why these were reported and not fixed** — three measured reasons, not caution theatre:
(a) un-hiding `bc-drive-plus` **adds 440 chars to a surface already over budget**, pushing ~1–2
tail skills dark, which is an owner trade-off, not a bug fix; (b) the budget-neutral alternative
is *deleting* 440 chars of authored text, and the destructive-action default forbids that on my
own initiative; (c) every description MODIFY is a permanent `DIVERGED` in the deploy hop across
three trees — the exact defect round 1 created and rounds 2–3 have been paying down.
Settling experiment for (a), for whoever takes it: restore the text, re-read the listing, and
check whether the boundary moves by ~440 chars as the greedy model predicts.

## What round 3 deliberately did not do

No new negative-case clauses. DoD item 4 is satisfied by round 2's seven, both reviewers
re-executed it, and the marginal clause is worth less than the risk: round 1's identical
"cheap safe edit" corrupted 21 files, and each edit adds permanent vault drift. Adding clauses to
the 30 dark skills would be **inert** — they do not render.

## Verification re-run at round-3 HEAD

| | |
|---|---|
| dual-write gate | `OK: no skills/ change lacks a .agents/skills/ counterpart.` exit 0 |
| main-guard, `dead_button_crawl.mjs` | `__isMain` present, old guard absent, `realpathSync` imported — in **all four** trees |
| main-guard, other `ui-audit/*.mjs` | repo 7/7 · `.agents` 7/7 · `skills.daily` 7/7 · **vault 6 still on the old guard** — item 2's open defect, unchanged, and proof the vault was not written |
| round-2 `V1..V7` | re-run, `SUCCESS:s2-r2-finalverify` |
| ruff 0.15.17 (the CI pin) | `check` + `format` clean on all round-3 probes |

> **Scope note on round-2's V5.** Its row reads "main-guard … present in **all four** trees",
> which is true **of `dead_button_crawl.mjs`** and false if read as the ui-audit directory: six
> vault entry points are still on the old lexical guard. Same fact, narrower sentence.

## Stale committed artifact, disclosed rather than rewritten

`S2-R2-BOUNDARY.json` as committed says `fleet: 115456`; `SKILLS2-ROUND2.md` says **115,461**.
Not a contradiction — the JSON was written at 04:21, *before* round 2's own `transcribe` repair
added 5 chars at ~05:3x, and the doc quotes a later probe. The committed round-1/round-2 JSONs are
**frozen receipts of what was measured then** and are left alone; the working tree holds the
verifier's re-runs, and round 3's own numbers live in `S2-R3-*.json`.