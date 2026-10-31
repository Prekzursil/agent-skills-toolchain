---
title: P11-CONFIRMATION
type: note
permalink: dqverify-repo-20261013/command-center/p11-confirmation
---

# PHASE 11 — INDEPENDENT CONFIRMATION (`depth/p11-confirmation`)

Spec `_USER-PROMPTS.md:11140-11153`. Fresh agent; wrote none of Waves 1-3. Every number below is
re-derived by nine probes written for this unit, off `git cat-file -p <named-commit>:<path>` bytes
for the baseline arms and off the working tree for the current arm. `git archive` is deliberately
not used — it returns CRLF on this box, so it is not the committed bytes.

Named anchors, never a moving reference: `W1_END=edcf9f5b` · `W2_END=0aa6f8fa` ·
`W3_END=04e4736c` (= HEAD at probe time) · intermediates `5e54207e`, `964cfa05`, `29f4c72a`,
`c1c51852`.

Machine-readable twin: `command-center/P11-CONFIRMATION.json` (carries the per-claim evidence,
the detector-control notes, and the new findings). Raw probe outputs: `P11-MUTATION-BOTHSTATES.json`,
`P11-FLOORS.json`, `P11-REGISTRY.json`, `P11-TRACKING-AND-IDS.json`, `P11-RERUNS.json`,
`P11-WAVE3.json`, `P11-D1.json`, `P11-EXPANSION.json`, `P11-TEST-DELTA.json`,
`p11_suite_full.log`, `p11_suite_platform.log`.

**STATUS: COMPLETE — 26 of 26 claims measured.** 18 CONFIRMED · 5 PARTIAL · 3 REFUTED.

## Headline

**The Wave-1 12/12 mutation battery scores 0/12 at the committed HEAD.** Wave 3's D1 fix
(`f5d1d4f2`) made `completion_predicate.py` import `vendor_identity` at module top level;
`_mutation_selfcheck.py` — last touched at `0e4a6751`, in Wave 1 — still copies only two files into
each mutant, so **all 12 mutants fail to import** and the tool emits
`FAILED:predicate-mutation-selfcheck survivors=[1, 2, ..., 12]`, exit 1. The repair exists **only
as an uncommitted working-tree edit that the D1-close lane explicitly disclaims**
(`D1-CLOSE-REGISTRY-GAP.md:375`, *"NOT mine"*), the tool appears in **no** `.github/workflows` or
`ci/` file, and the pytest suite is green throughout. Nothing on the committed tree detects it.

The control that makes this non-circular: the **same HEAD tool bytes** score **12/12 killed,
12/12 importable, exit 0** against a reconstructed Wave-1 tree (`edcf9f5b` predicate + schemas).
The regression is in the tree, not in the tool.

## Verdict table

| id | wave | sev | claim | verdict |
|---|---|---|---|---|
| W1-01 | 1 | P1 | registry 161 vs floor 160 | **CONFIRMED** — 164−1−2, 161 distinct, 0 dup ids |
| W1-02 | 1 | P1 | 48 protocols | **CONFIRMED** — structural classifier, 48 of 52 files |
| W1-03 | 1 | P1 | 69 presets | **CONFIRMED** — 69 of 73 tracked / 77 on disk |
| W1-04 | 1 | P2 | 8/8 schema docs compile | **CONFIRMED** — 8/8 then, 9/9 now |
| W1-05 | 1 | P1 | Wave-1 module set 444 passed | **CONFIRMED then superseded** — 515/0; 0 tests removed |
| W1-06 | 1 | P1 | mutation battery 12/12, 0 survived | **REFUTED at HEAD** (CONFIRMED as of Wave 1) |
| W1-07 | 1 | P1 | 0 of **269** output_schema paths exist | **PARTIAL** — 0 resolve ✓, denominator is **272** |
| W1-08 | 1 | P1 | 4 shells → 161−4=**157** | **PARTIAL** — 4 groups / 12 rows / excess **8** → **153** |
| W2-01 | 2 | P1 | 97 top-level blueprints, 0 dup ids | **CONFIRMED** at all three anchors |
| W2-02 | 2 | P1 | 65 flagship, 65/65 tested, 1111 passed | **CONFIRMED** — 1099 + the 65th file's 12 |
| W2-03 | 2 | P2 | 9 architectures + verdict + dissent | **CONFIRMED** — 40,120 B, 6-17 mentions, 0 dropped |
| W2-04 | 2 | P1 | forge REJECTs **and** CERTIFIEs | **CONFIRMED** byte-identical (5 / 2) |
| W2-05 | 2 | P1 | 233/233 cc-schema resolve, 36 unresolved | **PARTIAL** — 232/233, 39 unresolved |
| W2-06 | 2 | P1 | zero regression; suite 2767 | **CONFIRMED** no-regression; count superseded |
| W2-07 | 2 | P1 | 612 on disk, **0** git-tracked | **CONFIRMED** — 0/0/0/0/0 at `edcf9f5b` |
| W2-08 | 2 | P2 | 3 files share `fused.dc5b5f0b10f7` | **CONFIRMED** exact |
| W2-09 | 2 | P2 | stopping_rules = **2** normalised values | **PARTIAL** — 97 raw, 7 shapes, largest **87/97** |
| W2-10 | 2 | INFO | catalog **159** / 96 sentinels / 128 string-form | **CONFIRMED** all three exact; 128 → **0** now |
| W3-01 | 3 | P0 | D1 cross-vendor CLOSED | **PARTIAL** — 0 false greens at the pin; coverage gap real |
| W3-02 | 3 | P0 | D4 duplicate ids CLOSED | **REFUTED at `29f4c72a`** → 0 at HEAD |
| W3-03 | 3 | P1 | D3 test-mutates-tree CLOSED | **CONFIRMED** — 0 of 231 mtimes moved |
| W3-04 | 3 | P1 | check2 Phase 5 plugin PASS | **CONFIRMED the check ran**; briefed "never reached" **REFUTED** |
| W3-05 | 3 | P1 | check3 Phase 6 marketplace PASS | **CONFIRMED the check ran**; briefed "never reached" **REFUTED** |
| W3-06 | 3 | P1 | check6 regression NONE | **REFUTED as stated** — see the headline |
| E1 | 1 | exp | 6/6 valid pass · 10/10 invalid fire · 5+5 split | **CONFIRMED exactly** |
| E2 | 2 | exp | 14 skips = 11 + 3, no hidden failures | **CONFIRMED exactly** |

## The escalation rule fired — and the expansion exonerated the class

Threshold declared **before** measuring: >20% of a wave's claims REFUTED or PARTIAL expands that
wave's whole claim class. Measured — Wave 1 **3/8 = 37.5%** (tripped) · Wave 2 **2/10 = 20.0%**
(*at*, not above — stated rather than rounded up) · Wave 3 **3/6 = 50%** (tripped).

So re-verification expanded. For Wave 3 that meant abandoning sampling entirely: the D1 lane's
45-row matrix became the registry's **whole alias surface** (223 pairs at the pin, 247 now), the D4
summary became the **whole 6-commit chain**, and D3's 4-path sample became **all 231** generator
outputs. For Wave 1 it meant re-deriving the sharpest sub-section claim (E1).

**Every expanded sub-claim reproduced exactly.** That is the load-bearing result: the failure class
is *not* "these audits are unreliable". It is bounded to two things —

1. **exact counts asserted as stable** against a tree ~20 agents were mutating (W1-05, W1-07,
   W2-05, W2-06, W2-09 are all this), and
2. **consequence sentences wider than the measurement** that produced them (W1-08, W3-06, and
   Wave 3's "D1/D4 CLOSED" are all this — the code was right and the sentence overreached).

Mechanism claims and both-states controls — the parts that would be pure theatre if wrong — are
correct wherever I checked them: E1 hits 6/6 and 10/10 with the exact 5-schema-only / 5-semantics-only
split; W2-04's forge tournament reproduces to the fourth decimal; W2-03's verdict byte count is
exact; W2-10's 96 and 128 are exact; D3's guard asserts the positive over all 236 outputs.

## Three detector failures I made, caught, and fixed

Recorded because an uncorrected one would have shipped the opposite verdict.

1. **`upstream_repo` read at the top level** → 0 duplicate groups, which read as a refutation of
   F-W1-07. The field is nested under `provenance`. Pass 2 asserts it finds the known-present
   `WFA3-078`/`WFA3-073` pair before reporting any count.
2. **Vendor-registry shape guessed** (`vendors`/`entries`) → 2 identities and cross-vendor pairs
   answering `NOT-COMPUTABLE` while the probe's own control answered `CROSS-VENDOR`. A probe that
   contradicts its own control is a detector failure; pass 1's counts are void. Real shape is
   `identities[].{id, aliases, establishes_distinctness}`.
3. **`isinstance(d, dict)` mislabelled two JSON arrays "unparseable"** — `BP4-VALIDATION.json` and
   `BP7-VALIDATOR-OUTPUT.json` parse fine. The Wave-2 audit's "no unparseable files" is correct and
   mine was the error.

One insufficiency I could not remove, disclosed rather than folded into the green: the D3 mtime
census (0 of 231 changed) **would be silent in both states** if the generator only rewrote files
whose content differed. It is corroborated by a second, independent signal — `_run_generator(out_root)`
writes into `tmp_path`, and `test_running_the_generator_under_test_leaves_the_real_tree_untouched`
asserts the POSITIVE over every tracked digest — not carried alone.

## New findings, in no wave audit

- **P1 — `tools/marketplace/schema/` was never created.** 18 `output_schema` tokens the catalog
  references still do not resolve at HEAD, plus `.claude-plugin/marketplace.schema.json`. Commit
  `47cd5c11` is titled *"plugin **and marketplace** schema documents"* and its 18 added files are
  **all** under `tools/plugin/schema/` — zero marketplace schemas. Predicate condition 4 stays
  unsatisfiable for those units. Wave 2 predicted exactly this split and Wave 3 closed only one half.
- **P1 — the mutation-gate repair is an orphan.** Uncommitted, disclaimed by the only lane that
  mentions it, gating nothing. A fresh clone of HEAD gets 0/12.
- **P2 — 85 files across the five Wave-2 directories are untracked *and not gitignored*.**
  `git clean -xfd` still destroys them. Three are deliverables, not scratch: the two
  `platform/workflows/_shared/*.subworkflow.json` files the Wave-2 audit counted among its 103, and
  `command-center/schema/_meta/json-schema-2020-12.json`, which a work unit references — which is
  why a fresh clone resolves **232/233**, not 233/233. `platform/architecture` holds 103 files on
  disk against **10** tracked.
- **P2 — the suite-count war is a SCOPE error, not only a timing one.** Both arms measured here, both
  green: `cd platform/lib && pytest .` = **3,118 passed / 14 skipped / 0 failed**, and
  `python -m pytest platform` from the repo root = **3,922 passed / 14 skipped / 0 failed** in 614s.
  The second figure **reproduces Wave 3's `3922 passed, 14 skipped` exactly**, at a later HEAD — so
  that number is both correct and stable, and the apparent disagreement with 2,767 / 3,026 / 3,118 is
  a denominator difference, not a regression. No wave artifact but Wave 3's states its scope.
- **P3 — `forge` raises an unhandled `FileNotFoundError` traceback** on a bad `--source` path instead
  of a terminal `FAILED:` marker. Separately, the Wave-2 audit's "verbatim" forge transcript omits
  the mandatory `--source` arguments (`required=True` since `51156b0d`), so the recipe as printed
  exits 2 and does not reproduce.

## NOT-CHECKED — stated, never folded into a pass

- **Coverage %** anywhere: this project has no `.coverage-thresholds.json`, so coverage is
  NOT-CHECKED, not claimed.
- W2-10's **41** unresolvable dependency refs (needs the project's own SEM-001 bucket vocabulary).
  The sibling **159** figure was recovered and CONFIRMED: the pattern is
  `work-unit.normative.schema.json#/$defs/schema_reference`, and exactly **159 of 2,007** units fail
  it (first five: IMP-0001, IMP-0004, IMP-0005, IMP-0006, IMP-0008).
- Phase 8 **routing** precision/recall — outside the Waves 1-3 claim set.
- Substantive **plugin/marketplace lifecycle** behaviour, including the two revocation escapes.
  I confirmed only that Wave 3 *reached* those checks; Wave 4's two verify lanes own the behaviour.
- A **`git revert` rehearsal of the D1** registry/schema data change. Rollback was verified for
  W1-06 by tree reconstruction and for D4 by the commit chain, not by reverting D1.
- Wave-1's "52 non-blocking semantic warnings" / Wave-2's "largest role cluster 13" class of finer
  sub-numbers, and the **612 on-disk numerator** of W2-07 (that disk state is unrecoverable).

## Owner decisions this unit will not make

1. **The registry counting rule.** Floor 160 is MET at 161 only if every row counts. The audit's
   shell rule gives 157 (missed by 3); a uniform one-row-per-`upstream_repo` rule gives 153 (missed
   by 7). Its own 6-member `anthropics/claude-plugins-official` group shows upstream identity is not
   a duplication proof. This needs a ruling, not another measurement.
2. Commit the `_mutation_selfcheck.py` repair and wire the tool into a CI gate — or delete it.
3. Author `tools/marketplace/schema/` or retarget the 18 catalog references.
4. Track or explicitly ignore the 85 untracked-and-unignored files; three are deliverables.
5. The **239 of 261** `mcp__`-token units unapproved under `tool_policy.require_owner_approval`
   (carried from the D2 lane, deliberately not gated here).

Release mode is PR-ONLY, so program stopping condition 13 ("release/canary succeeds") is
unsatisfiable as written; read as "a merged PR plus a local rollback rehearsal" — and this unit
performed a rollback rehearsal only for W1-06 and D4, not for the release artifact.

---
`SUCCESS:depth/p11-confirmation` — 26 claims re-verified from raw source: 18 CONFIRMED · 5 PARTIAL ·
3 REFUTED · escalation tripped in waves 1 and 3, expansion reproduced exactly.