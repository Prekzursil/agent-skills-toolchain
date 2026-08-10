# LANE D1 — RE-VERIFY of PROMPT-ONE-FLOOR-AUDIT.md

**Measured:** 2026-08-10 · **Target:** `command-center/PROMPT-ONE-FLOOR-AUDIT.md` (measured 2026-08-09,
not this session) · **Method:** independent re-count with mechanically different anchors; read-only;
no catalog writes; no commits.

STATUS: **COMPLETE.** D1-1, D1-2, D1-3 all measured. All follow-ups concluded.

If it still reads this way, the unit died before investigating anything and no verdict here may be
cited. *(Contracted sentence, kept verbatim. It no longer describes this file — every section below
carries a measurement and a reproducible command.)*

COVERAGE: D1-1 MEASURED · D1-2 MEASURED · D1-3 MEASURED (**5 of 5** corrected probes independently
re-checked, plus IF-1). Nothing left UNKNOWN. Not covered by design: semantic (embedding) near-dup
scan — the audit's own declared residual, still NOT RUN.

**Bottom line: the audit is CORRECT on every number it reports. Its headline is UNDER-SCOPED.**
All 7 floors and the MD/JSON parity claim reproduce exactly under independent anchors. But "all 29
contracted artifacts exist" is a claim about **two untracked scratch directories on one machine**,
one of which is a **superseded 18-day-older program run**, and for the 4 filenames present in both
trees the "union" is **bidirectionally diverged with no precedence rule**.

---

## Proposals — items this lane owns

| id | current state | what I MEASURED | proposed disposition | evidence anchor | confidence |
|---|---|---|---|---|---|
| D1-1 union-scope | audit headline rests on "UNION OF TWO TREES" | **Neither tree is in version control** (git ancestor walk rc=128 from tree1, tree2 and `~`); **0 of 28** file-shaped artifacts in ast-integrate HEAD or worktree; 0 in agent-skills-toolchain / ast-harness-reconcile | **STAYS-OPEN** — headline needs an explicit scope clause; the union is also *ambiguous* (see N1) | `command-center/_d1_reverify_artifacts.out.json` → `version_control_status`, `counts` | almost-certain 90-99% |
| D1-2 single-tree recount | audit: 23 tree1 / 5 tree2 / 28 union / 0 missing | Reproduced exactly: tree1 **23/28**, tree2 **9/28**, union **28/28**, `missing_from_union` **[]**, same 5 tree2-only names as `PROMPT-ONE-FLOOR-AUDIT.md:82-84`. Committed repo alone: **0/28** | **CLOSE** — F7 is correct *on the scope the contract set* ("a dedicated, timestamped program directory") | `_d1_reverify_artifacts.out.json` → `sets` | almost-certain 90-99% |
| D1-3 five corrected probes | 5 probes self-reported as wrong-then-corrected | All **5** re-verified with mechanically different counters; all 5 corrections hold. IF-1 also re-verified after fixing a blind detector of my own | **CLOSE** with 4 scoping addenda (N4-N7) | `_d1_reverify_probes.out.json`, `_d1_reverify_followup.out.json`, `_d1_reverify_f345.out.json` | almost-certain 90-99% |

---

## D1-1 — WHICH two trees? (MEASURED)

Named at `PROMPT-ONE-FLOOR-AUDIT.md:23-28`:

- **tree1** `C:/Users/Prekzursil/.claude/harness-restore-20260806` — mtimes **2026-08-07/08**
- **tree2** `C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19` — mtimes **2026-07-20**

**Neither tree is in version control.** This is *stronger* than the lane hypothesis (which asked
whether the union merely *includes* an untracked tree). Two mechanically independent signals:

1. `git -C <tree> rev-parse --show-toplevel` → `rc=128`,
   `fatal: not a git repository (or any of the parent directories): .git` for **tree1, tree2 and `~`**;
   `rc=0` only for the repo. Git performs the full ancestor walk itself, so this rules out any
   enclosing repo.
2. `git ls-tree -r --name-only HEAD | grep -icE <artifact names>` over ast-integrate
   (**9,579** tracked files) → **0**. Same grep for `PROMPT-ONE-FLOOR-AUDIT` → **2**
   (**detector proven to fire on a known-present case**). Also 0 in `~/source/agent-skills-toolchain`
   and `~/source/ast-harness-reconcile`.

**Consequence.** On a fresh clone of ast-integrate: **0 of 29 artifacts**. The 29-artifact floor is a
single-machine working-filesystem property with no git backing, no clone reproducibility, and no
protection against loss. **In fairness to the audit:** the contract itself asked for
*"a dedicated, timestamped program directory"* (`_USER-PROMPTS.md`, `## Required artifacts` preamble),
so the audit measured what was contracted. The defect is the *undisclosed scope*, not the count.

**Required scoping edit (proposal, not applied — audit file is not mine to edit):** replace
"all 29 contracted artifacts exist" with "all 29 exist across two **untracked** program directories
under `~/.claude/`; 0 are in version control; a fresh clone has none."

## D1-2 — Re-count against a SINGLE tree (MEASURED)

Contract list parsed from `_USER-PROMPTS.md` itself, anchored on the `## Required artifacts` heading
(**not** line offsets — see N7). 29 items parsed → 28 file-shaped + item 29 (diagrams).
Triviality rule = the audit's own `<2KB`.

| scope | file-shaped present | non-trivial >=2KB |
|---|---|---|
| tree1 alone | **23 / 28** | 23 |
| tree2 alone | **9 / 28** | 9 |
| union | **28 / 28** | 28 |
| **ast-integrate HEAD (committed)** | **0 / 28** | 0 |
| ast-integrate working tree | **0 / 28** | 0 |

`missing_from_union` = `[]`. tree2-only set matches `PROMPT-ONE-FLOOR-AUDIT.md:82-84` exactly:
`02-BLOCKER-ROOT-CAUSE.md`, `04-MARKETPLACE-CURRENT-STATE.md`,
`06-EXISTING-WORK-ADOPT-EXTEND-RETIRE.md`, `10-WORKFLOW-FORGE-SPEC.md`, `12-COUNCIL-TEST-MATRIX.md`.

**The floor is NOT met on the repo alone — it is met on zero of it.** The audit's headline therefore
needs the scoping clause above; its *count* needs no correction.

## D1-3 — Independent re-verification of all five corrected probes (MEASURED)

Every counter below is mechanically different from the audit's counter for the same quantity
(different anchor / different field / different file / different tree).

| # | audit's corrected answer | my mechanically different counter | verdict |
|---|---|---|---|
| 1 | options **283 == 283**, sets identical | per-card FIELD lines: `- **default:**` **283**, `- **problem:**` **283**, `- **mechanism:**` **283**, `- **not a duplicate:**` **283**; JSON `options[]` 283 unique, 0 dupes; set equality **true** | **CONFIRMED** (4 independent anchors) |
| 2 | candidates **284 == 284** | **ALL** h3 headings in the doc = 284, of which backticked = 284, **unbackticked residue = 0**; JSON 284 unique; sets equal | **CONFIRMED** (residue-0 partition, immune to the truncation bug that caused the original error) |
| 3 | architectures **11** (columns, not rows) | h3-any-whitespace **11**; union of A-ids across all 5 markdown table header rows = exactly **{A1..A11}**; **and tree2's older copy of the same file, using a completely different convention (`## N. Candidate <n> —`), also yields 11** | **CONFIRMED** (5 signals total across 2 trees) |
| 4 | **8 of 8** diagrams | `diagrams/` holds 9 `.md`: 8 diagram files with **exactly 1** ` ```mermaid ` fence each + `README.md` with 0 | **CONFIRMED** (see N5) |
| 5 | **28/28** union, 0 missing | fully independent re-count (D1-2 above) | **CONFIRMED** |

**Bonus — IF-1 re-verified.** `13-ARCHITECTURE-CANDIDATES.md`: **38** distinct `MECH-NN` ids and
**exactly 2** bare `M-NN` lines, at **1159** (`adopt-after-M-16`) and **1193** (`adopt-after-M-21`) —
matching the audit's cited lines exactly.

**All other floors re-verified too (the parity claim in full).** F3 blueprints **108 == 108**, all h3
are BP cards (residue 0), sets equal. F4 protocols **58 == 58**, F5 presets **72 == 72**; total h4 in
the file = **130 = 58 + 72** with residue 0 and `protocols ∩ presets = ∅`; sets equal both ways.
Receipts: **0** occurrences of `"executed": true` in either JSON;
`status: "DISCOVERY - no protocol here has been executed"`, `discovery_only: true` — the audit's
"exists is not works" caveat is confirmed.

### Detector failures in THIS re-verification (disclosed to the audit's own standard)

1. **My contract parser mis-sliced (caught, fixed).** `_USER-PROMPTS.md` contains lone `\r` bytes, so
   Python universal-newline reading inserts extra line breaks and its line numbers **diverge from
   `grep -n`**. `lines[7828:7857]` landed on an unrelated bullet list → 9 items / 0 filenames. Fixed
   by anchoring on the `## Required artifacts` heading and splitting on `\r\n|\n`. See N7.
2. **My IF-1 counter was blind by construction (caught, fixed).** Lookbehind
   `(?<![A-Za-z0-9-])M-\d+` excludes `adopt-after-M-16` — precisely the two hits it was hunting. It
   reported **0**; the corrected regex `(?<!MECH-)\bM-\d+\b`, **proven to fire on a synthetic
   `adopt-after-M-16` and stay silent on `MECH-16` before use**, reports **2**.
3. **My "12th architecture" was a regex artifact (dissolved).** `A12` at lines 490 and 505 is
   `fan-out-contract §A12`, a rule-section citation. F6 = 11 stands.
4. **My "9 dangling option ids" dissolved on inspection.** `A-21 B-03 C-06 C-24 EV-15 H-03 PR-02
   PR-05 RT-14` are backticked in `07-OPTION-UNIVERSE.md` but absent from `options[]` — all
   explained by design: `A-21 (null-baseline)`, `B-03`/`C-06` `(anti-overfit-reject)` at lines
   142-144, and the remaining six appear **only** in the collapsed-merge pair list at line 3485
   (`C-23`+`H-03`, `RT-16`+`C-24`, `EV-22`+`EV-15`, `PR-01`+`PR-02`, `PR-04`+`PR-05`, `H-10`+`RT-14`).
   **Not a defect. Reported because the audit's credibility standard applies to me too.**

---

## New findings — NOT mine to close (proposals for the orchestrator / other lanes)

| id | pri | finding | evidence | confidence |
|---|---|---|---|---|
| **N1** | **P1** | **The "union" is ambiguous: all 4 filenames present in BOTH trees are BIDIRECTIONALLY DIVERGED documents, and the audit states no precedence rule.** Not line-ending noise (`identical_after_LF_normalisation: false`, 0 CRLF and 0 lone-CR on both sides). Each side holds unique lines — the exact two-directional case a one-directional read cannot see. `11-COUNCIL-SPECIFICATION.md`: tree1 **25,057 B / 447 lines / 11 h3** vs tree2 **126,045 B / 2,362 lines / 45 h3**, with **308** lines only in tree1 **and 1,566** only in tree2. `03-PLUGIN-LIFECYCLE-MAP.md`: 105,721 vs 38,274 B, 968/400 unique. `13-ARCHITECTURE-CANDIDATES.md`: 98,838 vs 98,891 B (near-identical size) but **14 vs 171** h3, 1,078/1,111 unique. `17-DECISION-LOG.md`: 45,443 vs 5,424 B, 286/73 unique. F6 is the only floor touched by the overlap, and it survives on both copies. **UNVERIFIED inline: I measured line-set divergence, which does not by itself prove semantic content loss — a "read the newer tree" rule would drop 1,566 unique lines from doc 11, but I have not classified what those lines carry. Settling experiment: section-level semantic diff of the 4 pairs.** | `_d1_reverify_followup.out.json` → `both_tree_divergence` | almost-certain 90-99% (divergence) / uncertain (loss) |
| **N2** | **P2** | **The audit's load-bearing union citation contradicts the audit — and the audit did not flag it.** `15-IMPLEMENTATION-PRECONDITIONS.md` ("Two trees, one contract" para) states *"`10-WORKFLOW-FORGE-SPEC.md` and `12-COUNCIL-TEST-MATRIX.md` exist only in `platform-redesign-2026-07-19`; **17** exact-named artifacts exist only in `harness-restore-20260806`"* — i.e. **2** tree2-only / 17 tree1-only. Measured: **5** tree2-only / **19** tree1-only. My measurement agrees with the *audit* (5), not with its cited corroboration. Per the specific-probe-wins rule the audit's number stands; the citation is stale (its tree1 count was a mid-run snapshot — the preceding paragraph names 4 artifacts still being written by lane `prompt-one-gaps`) and under-counts tree2-only by 3. `01-BLOCKER-REPRODUCTION.md:3-4` independently confirms only 1 of those 3. | `15-IMPLEMENTATION-PRECONDITIONS.md` "Two trees, one contract" para; `_d1_reverify_artifacts.out.json` → `sets` | almost-certain 90-99% |
| **N3** | **P2** | **5 of the 29 contracted artifacts are satisfied by a SUPERSEDED program run 18 days older.** Every tree2 file mtimes **2026-07-20 00:00-02:26**; tree1 mtimes **2026-08-07 16:55-20:32**. tree2 is the output of the earlier `platform-redesign-2026-07-19` program, structurally different (its doc 13 uses `## N. Candidate <n> —` + per-candidate `###` subsections). The union therefore mixes two program generations — a fact the audit's "two trees, one contract" framing does not surface. | `stat -c%y` on all 5 tree2-only + 3 tree1 samples; heading-style dump of tree2 doc 13 | almost-certain 90-99% |
| **N4** | P3 | **Item 29's constituents would fail the audit's own `<2KB` triviality rule: 4 of 8** diagram files are sub-2KB (`02-plugin-lifecycle.md` 1,601 · `03-marketplace-trust-flow.md` 1,991 · `05-review-verification-pipeline.md` 1,890 · `06-deployment-and-rollback.md` 1,627). The audit reports "0 trivial (<2KB)" and applied that test only to items 1-28. Counter-argument (why this is a rule-scope note, not a floor breach): item 29 is a *set* totalling **18,170 B**, and the contract says non-trivial per **item**. | `_d1_reverify_followup.out.json` → `diagram_triviality` | almost-certain (the byte facts) / likely 55-80% (that a reviewer calls it a real gap) |
| **N5** | P3 | Audit says `diagrams/` "holds exactly 8 `.md` files"; it holds **9** — 8 diagrams + `README.md` (0 mermaid fences). Cosmetic; the substantive 8-of-8 claim is correct. | `_d1_reverify_artifacts.out.json` → `item29_diagrams.files` | almost-certain 90-99% |
| **N6** | P3 | Audit says "23 in tree 1, **5** in tree 2". 5 is the tree2-**ONLY** count; tree2 holds **9** of the 28. The wording hides the 4-file overlap that creates N1. | `_d1_reverify_artifacts.out.json` → `counts` | almost-certain 90-99% |
| **N7** | P3 | **The audit's contract citations `_USER-PROMPTS.md:7829-7857` are reader-dependent.** The file carries lone `\r` bytes, so a `\n`-only reader (`grep -n`) and a universal-newline reader (Python `open()` default) disagree about which line is 7829. Anyone re-deriving the contract from those offsets in Python gets the wrong block (measured — it cost me one probe). Cite the `## Required artifacts` heading anchor instead. | this file, "Detector failures" #1; `_d1_reverify_artifacts.py` `contracted_items()` docstring | almost-certain 90-99% |

---

## Reproduce

```
python command-center/_d1_reverify_artifacts.py   # 29-item count: per-tree, union, repo HEAD, worktree
python command-center/_d1_reverify_probes.py      # F1/F2/F6 + IF-1 via mechanically different anchors
python command-center/_d1_reverify_followup.py    # A12, dangling ids, both-tree divergence, IF-1 fixed
python command-center/_d1_reverify_f345.py        # F3/F4/F5 + full MD/JSON parity + receipt check
```
Outputs: `_d1_reverify_*.out.json` in this directory. Every probe carries an in-band detector
control; `_d1_reverify_artifacts.out.json` → `detector_control.PASS` is `true`.

**Self-application of D1-1 (disclosed).** These four probe scripts are **gitignored** —
`git check-ignore -v` → `.gitignore:70: command-center/_*.py`. So my *own* evidence is
working-tree-only and would not survive a fresh clone either, exactly the defect this lane reports
against the audit. The `.out.json` results are untracked-but-not-ignored and are committable; the
scripts are not. Whoever consumes this file should either commit the scripts under a non-ignored
name or treat the `.out.json` payloads as the durable record.
