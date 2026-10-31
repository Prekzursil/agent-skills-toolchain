---
title: PHASE14-SYNTHESIS
type: note
permalink: dqverify-repo-20261013/command-center/phase14-synthesis
---

# PHASE 14 — SYNTHESIS AND META-REVIEW

- **Unit:** `synthesis/phase14` · **Spec:** `_USER-PROMPTS.md:11084-11098`, scored against `:11376-11398`
- **Tree:** `04e4736c` on `main`, **0 ahead / 0 behind `origin/main`**, plus an uncommitted Wave-4 delta
  (763 changed-or-untracked entries under `git status --short -uall`)
- **Date:** 2026-08-10
- **Machine twin:** [`PROGRAM-STOPPING-SCORECARD.json`](PROGRAM-STOPPING-SCORECARD.json) — kept in step
  with this file; every claim here has its evidence field there
- **Status:** COMPLETE — manifest verified on disk, 21 of 21 stopping conditions scored,
  root-cause hierarchy and decision trace produced, 7 named failure modes meta-reviewed

**STATUS: 2 TRUE / 19 FALSE / 0 NOT-CHECKED. The program is not stoppable.**

The useful result is not the count. It is condition 21: **the shared completion predicate is
self-certifying**, so a TRUE there would have been evidence of nothing. That single fact reframes
every other row — the program's problem is not that it failed its gates, it is that its central
gate cannot tell work that happened from work that claimed to.

**COVERAGE.** 14 of 21 conditions scored from measurements taken by this unit. 7 rest on sibling
lanes' on-disk executable receipts that I read but did **not** re-execute (conditions 4-Linux-arm,
5, 6, 7, 9, 11, 14) — marked `evidence_origin: sibling-receipt` in the JSON. A receipt I did not
re-run is one signal, not two, and I say so per-row rather than in a footer.

---

## 1. Artifact-manifest verification on disk — the spec's precondition for this report

Spec `:11098` requires the final synthesis agent to verify the manifest on disk *before* writing a
completion report, because "a file path in text is not proof the file exists" (`:10646`). Done, with
a detector control that passed before any count (known-present path detected; known-absent control
path not detected). Probe: `command-center/_p14_manifest_verify.py` → `P14-MANIFEST-VERIFY.json`.

**Finding: the manifest is NOT verified on disk, while asserting `"verified_on_disk": true`.**

| result | n |
|---|---|
| listed | 14 |
| missing on disk | 0 |
| sha matches working-tree bytes | 3 |
| sha matches **LF-normalized** bytes | 9 |
| self-entry (cannot hash itself) | 1 |
| **SHA MISMATCH** | **1** |

The 9 LF matches are correct behaviour, not a defect — `render_manifest` deliberately LF-normalizes
before hashing so a Windows-authored manifest can satisfy `--check` on Linux CI. I report both
digest forms per path precisely so that design choice cannot be mistaken for drift.

The one real mismatch is `command-center/DEPENDENCY-GRAPH.json`:

| | bytes | sha256 |
|---|---|---|
| manifest records | 25,317 | `d78b96db…` |
| on disk | 25,261 | `eda25730…` (raw **and** LF — identical, so no CRLF involved) |

`git cat-file -p HEAD:command-center/DEPENDENCY-GRAPH.json \| wc -c` = **25,317** exactly. The
manifest is recording the *committed blob* while the working tree holds an uncommitted edit.

**Root cause — `tools/command-center/render.py`, `write_all()`:** the manifest is rendered at
`:299-300`, hashing `DEPENDENCY-GRAPH.json` as it currently sits, and the graph is only rewritten
*afterwards* at `:311-312`. Any catalog edit that changes the derived graph therefore leaves the
manifest holding the previous generation's hash. The comment at `:303-310` added the graph write
specifically *to make the procedure converge* — it converted a `V-GRAPH` drift into an
`ARTIFACT-MANIFEST` drift rather than removing it.

Three independent signals agree:

1. my hash probe (above);
2. the program's own gate — `python tools/command-center/render.py --check` →
   `ARTIFACT-MANIFEST.json does not match the files on disk` / `FAILED:cc-render drift=1`, **exit 1**;
3. `.github/workflows/quality.yml:403` runs that exact check, so **this working tree is CI-red**.

**It was seen twice before and explained away both times.** `platform/DEFECT-D1-CROSS-VENDOR.md:12`
attributes `cc-render drift=1` to "a sibling's in-flight catalog" and `:236` disowns it as "NOT this
unit's". That is a Phase-13 "failure normalized away" instance found inside the tooling built to
prevent it.

**Manifest coverage.** 386 deliverable files sit under `command-center/`; 14 are registered. That is
**not** automatically a defect — the manifest declares its scope as the 13-file charter contract
(`:10590-10603`). The consequence is what matters: completion-predicate condition 11 ("output was
registered in the artifact manifest") has no registry to check the other 372 against, and the
intersection of the 2,007 catalogued `output_path`s with this manifest is **0**.

---

## 2. Root-cause hierarchy

Not a flat list. Six causes, one apex, with the parent edges that make them a hierarchy.

```
RC-0  no execution ledger — plan and delivery are disjoint namespaces
├── RC-1  the shared completion predicate is SELF-CERTIFYING
│   └── RC-3  static validation mistaken for capability (no executor, no council runtime)
├── RC-2  instruments built but never wired to a gate
│   ├── RC-4  tests coupled to the operator's LIVE machine
│   └── RC-5  ordering defect makes the artifact-integrity gate self-inconsistent
└── RC-6  no owner decision recorded — the program's scope is an executor assumption
```

### RC-0 — APEX. No execution ledger, so plan and delivery cannot be reconciled

The 2,007-unit catalog carries 20 planning fields on 2007/2007 units and **zero**
status/disposition/receipt field.

| signal | method | result |
|---|---|---|
| S1 | per-path `stat()` + non-emptiness over every declared `output_path` | **2** of 2,007 |
| S2 | set intersection of declared paths against 8,911 git-tracked files | **2** |
| S2b | same intersection against `ARTIFACT-MANIFEST.json` | **0** |
| S3 | mechanically different filename/stem + unit-id scan (`DELIVERY-RECONCILIATION.json`) | **30** of 2,007 = **1.49%** |

S3 is a genuinely independent instrument (`reconcile_delivery.py`, 8,814 text files scanned for unit
ids) and it *widens* the count without changing the verdict — 2 is the lower bound at the declared
path, 30 the upper bound on filename evidence, and that lane says so itself: a basename match proves
an artifact of that *name* exists, not that it satisfies the unit's `evidence_requirement`.

Whole expected output directories were never created: `receipts` (1,021 units), `adversarial` (144),
`design/council` (128), `research` (128), `confirmation` (127), `audit` (96), `foundry` (32),
`synthesis` (25).

**Why this is the apex, and why it is not "the program did nothing".** Delivered work is real —
8,911 tracked files, a 3,922-test green suite, plugin + marketplace + routing all shipped. It simply
lands in a path namespace the catalog never references. With no ledger joining the two, "done" can
only be self-reported. That is what makes downstream completion claims *unfalsifiable* rather than
merely wrong, and it is why every remaining cause is a child of this one.

### RC-1 — The completion predicate is self-certifying

Five of twelve conditions (7 tests, 8 mutations, 9 reviewer, 10 defects, 12 consumers) are satisfied
by reading fields the receipt writes about itself. I confirmed the mechanism in source rather than
taking the refuter's word:

- `platform/lib/completion_predicate.py:804-843` — `_c7_tests` accepts a record when
  `result == "PASS"` and `command` is a non-empty string. **The command is never executed** and no
  test log is consulted.
- `:918-923` — rejects only when `independent is not True`. That flag is set by the receipt about
  itself.

The refuter lane has the executable proof: a forged receipt in which no test process started, no
control ran, and `reviewer.reviewer_id == produced_by.agent` returns **COMPLETE, satisfied=12/12,
not_checked=0**, emitting `SUCCESS:ZZ-0001 predicate=COMPLETE satisfied=12/12`.

This is the *guard-converts-a-bug-into-a-green* shape at program scale, and it is aggravated by the
docstring: the file claims a self-certifying receipt is "the failure this predicate exists to
prevent."

### RC-3 — Static validation mistaken for capability

| probe | result |
|---|---|
| `def execute` / `def run_workflow` / `class WorkflowExecutor` / `def _execute_stage` over `platform/lib/wfdsl`, `platform/workflows`, `platform/lib/*.py` | **0 files** |
| `class CouncilRuntime` / `def run_council` / `class CouncilCompiler` / `def compile_council` / `def deliberate` over all of `platform/` | **0 files** |
| **DETECTOR CONTROL** — `def validate` / `def resolve` in the same tree | **3 files** |

The control proves both zeros are real. `platform/lib/wfdsl/` is `authz_census, capabilities, expr,
mutations, resolve, schemas, semantics, validate`; `platform/lib/councilspec/` is `expression,
registry, semantics, validate, make_negatives`. Both are validators.

So "97 **executable** blueprints" and "**universal council runtime**" are schema-and-validator
achievements. The artifacts are real, distinct (4,656 pairs checked on two axes) and their tests are
green — the *verb* is not earned. This is the C2 overclaim pattern (code correct, sentence wider than
the evidence) landing on the program's two flagship deliverables. A refuter reached the same
conclusion structurally when it could not test prompt injection into a later stage: "no executor
exists."

### RC-2 — Instruments built, never wired to a gate

- `platform/` appears **0 times** in all 7 workflow files. **Control:** the same grep finds
  `command-center` 5, `monitorcore` 22, `mcpctl` 28 — so the zero is real. The 3,922-test suite is
  required by no automated gate.
- The 12/12 mutation battery scores **0/12** at committed HEAD: the D1 fix added a module-level
  `vendor_identity` import and `_mutation_selfcheck.py` still copies only two files into each mutant,
  so all 12 mutants fail to *import*. The repair is an uncommitted orphan the only lane that touched
  it disclaims; the tool is in no workflow. A fresh clone of HEAD gets 0/12. **Non-circular control:**
  the same HEAD tool bytes score 12/12 killed against a reconstructed Wave-1 tree — the regression is
  in the tree, not the tool.
- The one CI job named for routing tests a **different** router (`hooks/semantic-router`), and its
  regression probe is `continue-on-error: true`.
- The one command-center gate that *is* wired is currently **red** (RC-5).

### RC-4 — Tests coupled to the operator's live machine

`platform/routing/index.py:55`:

```python
HOME = Path(os.environ.get("ROUTING_HOME") or Path.home())
```

The capability corpus under test is the operator's **live `~/.claude` harness**, not a committed
fixture. Windows: 27 agents / 71 commands / 79 skills → 912 capabilities. Linux `$HOME`: 0/0/0 → 383
records, and the test's own implausibly-small floor fires (`assert 383 > 800`).

| | failed | passed | skipped |
|---|---|---|---|
| Ubuntu 24.04 / py3.12.3 | **24** | 3,875 | 37 |
| Windows (my run) | **0** | 3,922 | 14 |

22 of the 24 are `platform/routing`, 2 `platform/coordination`. **Control:** `platform/plugin` on the
same Linux interpreter gives 252 passed, so "the build breaks on Linux" is REFUTED — the failures are
localised.

Two consequences at once: every Phase-8 figure is a property of one box and is **not reproducible on
another host**, and the absent `platform/` CI lane is **forced by the design**, not merely forgotten.
The fix seam exists and no test uses it: `ROUTING_HOME`.

**Credit where due:** those tests assert the POSITIVE form (N of N, plus an explicit
implausibly-small floor), which is exactly why this coupling surfaced instead of passing vacuously on
a 383-record corpus.

> **IN-FLIGHT — RC-4 is being fixed as this document is written.** While I was measuring, a sibling
> lane (`routing-hermetic`) added `platform/routing/conftest.py` (+111 lines, untracked→modified
> during my run) which binds `ROUTING_HOME` to a committed fixture under
> `platform/routing/fixtures/home/` and carries the both-states control (with the fixture the suite
> passes; with an empty directory the corpus floor fires). That is exactly the seam RC-4 and P13
> named. **Consequence for this report:** my RC-4 evidence and conditions 4, 7 and 8 are anchored to
> commit `04e4736c` plus the uncommitted delta present *at my measurement time*, and that delta has
> since grown. I am not re-scoring on a reference that is still moving — re-run this scorecard after
> that lane lands. The Linux 24-failure figure and the "912 capabilities are machine-specific" claim
> were true when measured and may be superseded by that fix.

### RC-5 — Ordering defect in the manifest renderer

Fully evidenced in §1. Parent is RC-2 because the gate exists and is wired; what failed is that a
convergence fix was inserted on the wrong side of the hash.

### RC-6 — No owner decision recorded; scope is an executor assumption

- **27 of 27** owner questions OPEN, zero answered.
- The spec's three owner-input slots still hold literal placeholders: `:10516`
  `[PASTE SELECTED OPTION IDS HERE]`, `:10520` `[PASTE OWNER OVERRIDES HERE]`, `~:10524` the
  release-mode choice.
- **OQ-3 (release mode) is OPEN** and `OWNER-DECISIONS.md` records that Phase 15 branches entirely on
  it — yet PR-ONLY is treated as binding, *including by my own spawn brief*, with no decision record
  anywhere in `command-center/`.
- **OQ-4** — was the ~38-item harness tranche an approved substitute for the ≥2,048-unit program? No
  approval record exists. This is the owner-facing form of RC-0.
- `work_units_meta`: target 2048, count 2007, **shortfall 41** — a declared shortfall never closed, on
  top of the 2,006 unexecuted.

Consequence: condition 1 cannot be scored TRUE by *any* measurement, because nothing was ever
**selected**. The "selected quality tiers" clause in condition 17 and the "selected support contract"
clause in condition 7 are likewise unscoreable on their own terms.

---

## 3. Decision trace

| # | decision | recorded where | consequence |
|---|---|---|---|
| D-a | Spec demands ≥2,048 work units; a 2,007-unit catalog was authored (shortfall 41 declared) | `WORK-UNIT-CATALOG.json` `work_units_meta` | the plan exists |
| D-b | The catalog was given **no** disposition/receipt field, and the existing `close.py`/`render.py` disposition pipeline was not used for it | absence, measured | **RC-0** — no ledger |
| D-c | Execution proceeded as a ~38-item harness tranche instead | `OWNER-DECISIONS.md` OQ-4, unanswered | scope substitution, unapproved |
| D-d | A shared completion predicate was written, with 5 of 12 conditions self-declared | `completion_predicate.py:804-923` | **RC-1** — the gate cannot falsify |
| D-e | `ARTIFACT-MANIFEST.json` scoped to the 13-file charter, not to unit outputs | manifest `contract` field | predicate condition 11 has no registry → intersection 0 |
| D-f | `platform/` was never added to CI | 0 hits in 7 workflow files | **RC-2** — regressions invisible |
| D-g | Routing indexed the live `~/.claude` rather than a fixture | `index.py:55` | **RC-4** — CI absence forced; figures machine-specific |
| D-h | Wave 3 shipped D1/D4 fixes and asserted CLOSED early | Wave-3 audit | overclaim; **both are genuinely closed today** (§5) |
| D-i | The D1 fix added a top-level import; the mutant builder was not updated in the same commit | `_mutation_selfcheck.py` | mutation battery 0/12 at HEAD |
| D-j | A graph-write was appended to `write_all()` *after* the manifest render, to fix convergence | `render.py:303-312` | **RC-5** — drift moved, not removed; CI red |
| D-k | Wave 4 ran independent confirmation, refutation, blind-spot and three verify lanes | P11/P12/P13, WAVE4-* | the defects above became visible and citable |
| D-l | Wave 4's entire output was left untracked | `git status -uall` | condition 13 FALSE; `git clean -xfd` would destroy it |

---

## 4. Meta-review — the seven failure modes the spec names

| failure mode | verdict | the sharpest instance |
|---|---|---|
| unsupported certainty | **PRESENT, declining** | the manifest's `"verified_on_disk": true` (false right now); the predicate docstring claiming to prevent self-certification; "97 **executable**" and "council **runtime**" |
| omitted dissent | **LARGELY ABSENT** — best axis | 9 architectures + verdict, 6-17 dissent mentions, 0 dropped; every Wave-4 lane records its own refuted claims in place |
| duplicate mechanisms | **PRESENT** | two registers (103-item with disposition machinery vs 2,007-unit without) and two routers (`platform/routing` = deliverable, zero CI; `hooks/semantic-router` = what CI gates, fail-open) |
| stale evidence | **PRESENT** — bit my own brief on 4 of 5 points | D1, D4, the 3,026 baseline, "routing self-reported" — all corrected in §5 |
| missing artifacts | **PRESENT** — largest single gap | 2,005 of 2,007 output paths absent; `tools/marketplace/` absent with 18 dangling refs; no STRIDE model; no SBOM instance, license inventory, vuln scan or changelog |
| code/docs mismatch | **PRESENT** — 5 live | manifest flag · predicate docstring · `RELEASE-CHECKLIST.md:19`'s `git archive` recipe (returns **CRLF** here, so it verifies the wrong bytes) · stale routing dedupe comment · present-tense `M-NN` collision at `17-DECISION-LOG.md:175` |
| completion claims not backed by the predicate | **PRESENT** — the one finding to keep | see below |

**On the last row, which subsumes the rest.** Nothing in this program is backed by the shared
predicate, in two distinct senses. *Mechanically:* 2,007 units produced 0 receipts, so the predicate
was never run for them — intersection with the manifest is 0. *Substantively:* where it **is** run it
cannot distinguish work that happened from work that claimed to, because five of its twelve conditions
read self-declared fields and a forged receipt scores 12/12. So condition 21 is simultaneously false
for the program and, were it true, uninformative. Every completion claim therefore rests on
lane-level evidence — which on the Wave-4 sample is frequently excellent — and not on the shared gate
the spec designed to carry it.

**On "unsupported certainty declining":** the counter-evidence is real and I weight it. Phase 11
bounded the failure class to two shapes — exact counts asserted as stable against a tree ~20 agents
were mutating, and consequence sentences wider than their measurement — and found 5 of 8 refutations
were *overclaims, not broken code*. Wave-4 lanes lead with their own detector failures and mark
NOT-CHECKED instead of folding to a pass. That is the opposite failure mode, and it is being avoided.

---

## 5. Corrections to my own spawn brief — four of five points were stale

My brief named four items as "left open" by Wave 3. Measured at today's tree, **two are closed**, one
is resolved, and one pinned number is wrong. I record these as corrections rather than quietly
scoring around them.

| briefed | measured today | how |
|---|---|---|
| **D1 NOT CLOSED** — the fix over-corrected; 13 of 45 pairs NOT-COMPUTABLE because "Anthropic PBC" → `anthropic-pbc` is absent from the registry | **REFUTED — D1 IS CLOSED.** `same_vendor_rows_NOT_COMPUTABLE: 0`, `same_vendor_rows_ACCEPTED_as_cross_vendor: 0`, `incorrect_rows: 0`, `ALL_ROWS_CORRECT: true`. The 13 NOT-COMPUTABLE rows are **exactly** the 13 `refusal_rows` — rows whose expected verdict *is* a refusal — all 13 blocked, 0 leaked. Registry now 21 canonical ids / 130 recognized tokens. | I re-ran the lane's own re-runner: `python command-center/d1_close_matrix.py --out …` → `SUCCESS:d1-close-matrix all rows correct, both-states controls valid`; tallies reproduce the stored JSON exactly. Both controls valid: the re-implemented pre-fix gate leaks **44/44**, the shipped gate leaks **0** |
| **D4 NOT CLOSED** — two files still share one id | **REFUTED — D4 IS CLOSED.** 126 files parsed, 0 unparseable, 102 distinct ids, **0 duplicate groups**. `fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json` is ABSENT; only `forged/fused.cnc07-arc05.workflow.json` remains | my own scan, with a **planted-duplicate control** that fired |
| **the suite is 3,026 passed / 14 skipped** — "if you quote a baseline, quote this one" | **REFUTED — 3,922 passed / 14 skipped / 0 failed**, exit 0, 571.48 s. Matches Wave 3 and P11 exactly. The disagreement is **scope**: `cd platform/lib && pytest .` gives 3,118. So 3,026 is the *fourth* successive baseline correction (2,767 → 2,812 → 3,026 → 3,922) | my own `python -m pytest platform -q` from the repo root → `command-center/_p14_suite_platform.log` |
| **routing SELF-REPORTED** — the audit's probe crashed on `SemanticModel.build` | **PARTIAL — resolved.** The crash was the *probe's* error: the class exposes `fit()`, not `build()`; `Router.build()` exists at `router.py:279`. A Wave-4 lane re-measured and agreed on **1,239 of 1,239** decisions, 0 disagreements, all 12 tier-by-k rows exact. What remains worse than "self-reported" is that the figures are machine-specific | sibling receipt, read not re-run |
| **plugin + marketplace UNVERIFIED** | **SUPERSEDED — verified-with-defects.** Plugin: 5 checks, deterministic package, 5 verbs CONFIRMED, 2 PARTIALs. Marketplace: 6/6 checks with both-states controls, 162 tests, 8-path revocation hunt → **2 CONFIRMED escapes** | sibling receipts |

The `239 of 261` unapproved `mcp__`-token units in my brief **reproduces** and stays an owner
decision, surfaced not gated.

---

## 6. The 21 stopping conditions

Full evidence and settling experiments per row: [`PROGRAM-STOPPING-SCORECARD.json`](PROGRAM-STOPPING-SCORECARD.json).

| # | condition | verdict |
|---|---|---|
| 1 | every selected option implemented / superseded / rejected with owner approval | **FALSE** — nothing was ever *selected*; 27/27 OQs open |
| 2 | all contracted artifacts exist and pass schema/manifest checks | **FALSE** — manifest drift=1; `tools/marketplace/` absent (18 dangling refs); 2 of 2,007 at declared path |
| 3 | all P0/P1 closed or externally blocked | **FALSE** — the two briefed P0s are closed, but ≥4 P1s live |
| 4 | no required test is red | **FALSE** — a wired CI gate exits 1; Linux 24 failed; and `platform/` is required by nobody |
| 5 | mutation and negative-control coverage demonstrate detector validity | **FALSE** — flagship battery 0/12 at HEAD, repair orphaned |
| 6 | clean install, update, rollback, uninstall pass | **FALSE** (PARTIAL) — 5 verbs CONFIRMED; hard-kill leaves a blocking lock; health check tests existence not integrity |
| 7 | cross-platform / cross-client matrices meet the support contract | **FALSE** — no contract; macOS never run; only `claude-code` tested; all 13 CI jobs ubuntu |
| 8 | benchmarks show the intended improvement without regression | **FALSE** — figures machine-specific; abstention false-fires 24/36; k=10 buys zero recall |
| 9 | independent confirmers pass | **FALSE** — ran, returned 18 CONFIRMED / 5 PARTIAL / 3 REFUTED; escalation tripped in 2 waves |
| 10 | adversarial refuters cannot produce an unresolved load-bearing counterexample | **FALSE** — an executable one exists and is unresolved |
| 11 | security / privacy / legal / supply-chain gates pass | **FALSE** — 2 CONFIRMED revocation escapes; no STRIDE; privacy + legal NOT-CHECKED |
| 12 | docs and code agree | **FALSE** — 5 live mismatches |
| 13 | release/canary succeeds | **FALSE** — unsatisfiable as written; see §7 |
| 14 | rollback is tested | **TRUE** — scoped to the plugin package's rollback verb |
| 15 | every residual unknown has a settling experiment + impact statement | **FALSE** — 13 well-formed rows, but no Wave-4 residual was added |
| 16 | ≥160 candidates classified with provenance/license | **TRUE** — 163 of 163 non-manifest rows |
| 17 | ≥96 materially distinct blueprints **executable** | **FALSE** — 97 exist and validate; **no executor** |
| 18 | scout/forge, merge maps, tournament, lineage/decomposition tests pass | **FALSE** — 267 tests green, but **merge/compatibility maps do not exist** |
| 19 | council **runtime**, 48 protocols, 64 presets, anti-sycophancy, dissent, Boolean stopping, council-of-councils | **FALSE** — every floor met (48/69), tests green, **no runtime** |
| 20 | the final synthesis has been meta-reviewed | **FALSE** — this document is un-reviewed single-agent output |
| 21 | the shared completion predicate returns true for the program | **FALSE** — and it is **not a gate** |

**Why 21 TRUE would be the thing to disbelieve.** Six of the 21 reference owner selections that were
never made ("every *selected* option", "the *selected* support contract", "the *selected* quality
tiers", the release mode). Those are not merely unmet — they are **unscoreable on their own terms**
until OQ-1 and OQ-3 are answered. A 21/21 scorecard would necessarily have scored them by assumption.

### Detector corrections I made while producing this

Recorded because an uncorrected one would have shipped a wrong verdict.

1. **Directory mis-discovery.** My floor probe's fallback loop found `platform/council/protocols` and
   labelled it *presets*, then reported `protocols>=48: false` **and** `presets>=64: false` while
   holding a count of 48 shaped files. A probe that disagrees with itself is a detector failure, not a
   finding — I fixed the paths (`council/protocols` = 52 files / 48 shaped; `council/presets` = 77 /
   69) and replaced the silent fallback with an assert.
2. **`isinstance(provenance, dict)`.** Reported only 130 of 164 candidate rows as having provenance.
   Measured value types: dict 130, **list 33**, missing 1 (the manifest row). The list-valued rows are
   fully populated; my type assumption was the bug, and the corrected count is 163 of 163. This is the
   *same class* P11 recorded as its own detector failure #3 — an `isinstance(dict)` test mislabelling
   JSON arrays — reproduced by me, which is why it is written down rather than quietly patched.
3. **Absence claims gated on controls.** Every zero above carries one: the executor/runtime greps are
   validated against `def validate|def resolve` → 3 files; the merge-map absence against `tournament`
   → 3 files; the D4 zero against a planted duplicate id; the manifest walk against a known-absent
   control path.

---

## 7. Condition 13 — how I read it, and the premise that undercuts my own reading

Under PR-ONLY there is no canary to succeed, so I read condition 13 as **"a merged PR carrying this
program's work, plus a local rollback rehearsal of the release artifact."**

Scored **FALSE** on that reading: `git rev-list --left-right --count origin/main...HEAD` = `0 0`,
`gh pr list` returns no open PR, and the entire Wave-4 output is untracked — no PR carries it. Phase
15's deliverables are absent besides the package: no version-bump record, changelog, migration guide,
signed artifact, provenance attestation, SBOM instance, license inventory, vuln scan, or
compatibility-matrix instance (only *schemas* for the last two).

**The premise I will not paper over.** PR-ONLY is an **executor assumption**, not a recorded owner
selection. Spec `~:10524` still holds the literal placeholder, OQ-3 is OPEN, and
`OWNER-DECISIONS.md` records that Phase 15 branches entirely on it. My own brief asserts "Release
mode PR-ONLY is binding"; I could find no decision record for that anywhere in `command-center/`. So
my re-reading rests on an unrecorded premise, and I flag the contradiction rather than adopt either
side. **Settling experiment:** answer OQ-3 and record it through `close.py` so it lands in
`events/EVENTS.jsonl`.

---

## 8. What genuinely works — stated because a 19-FALSE scorecard is easy to misread

| | |
|---|---|
| platform suite | **3,922 passed / 14 skipped / 0 failed** on Windows, re-run by me, exit 0 |
| D1 vendor identity | **CLOSED**, re-derived by me today, two both-states controls valid |
| D4 workflow-id uniqueness | **CLOSED**, 102 distinct ids / 126 files / 0 duplicates, planted-duplicate control fired |
| plugin package | deterministic — byte-identical sha256 across two builds and identical to the committed dist zip; 95,093 B / 45 entries; no `.git`, credentials or transcripts; conformance validator fails **9/9** seeded mutants; all five lifecycle verbs work |
| marketplace | **6 of 6** required checks pass, each with a both-states control; 162 tests green; an 8-path revocation hunt that actually found two escapes |
| routing arithmetic | **1,239 of 1,239** decisions agreed on independent re-measurement; 12/12 tier-by-k rows exact; four both-states controls including a flood control at **133×** |
| numeric floors | 48 protocols · 69 presets · 97 blueprints · 163 candidates — all met, each counted with a control-tested classifier |
| the Wave-4 lanes | P11, P12, P13 and the three verify lanes each led with their **own** detector failures, marked NOT-CHECKED rather than folding to a pass, and corrected over-counts in place. That is the behaviour the spec's honesty instrumentation asked for, and it is the reason this scorecard could be written at all |

---

## 9. Owner decisions needed

1. **OQ-3 — the release mode.** Treated as PR-ONLY with no record; condition 13 and all of Phase 15
   branch on it.
2. **OQ-4 — was the ~38-item tranche an approved substitute for the ≥2,048-unit program?** No approval
   record. The owner-facing form of RC-0.
3. **OQ-1 — select the option IDs.** 283 options intact, none selected; condition 1 is unscoreable
   until this is answered.
4. **Do predicate conditions 7/8/9/12 become MEASURED** (the reducer executes test commands and
   consumer probes — a large change in what a reducer *is*), or stay self-declared with the citation
   practice changed so `predicate=COMPLETE` is no longer cited as evidence those four properties hold?
5. **The candidate-registry counting rule** — 163 / 161 / 157 / 153 depending on the rule; the floor of
   160 is met by the first two and **missed** by the last two.
6. **Commit the `_mutation_selfcheck.py` repair and wire it into CI, or delete it.** Today a fresh
   clone scores 0/12.
7. **Author `tools/marketplace/schema/`** or retarget the 18 catalog references.
8. **Track or explicitly gitignore the 85 untracked-and-unignored files** — three are deliverables, so
   `git clean -xfd` destroys real work.
9. **239 of 261 `mcp__`-token units are UNAPPROVED** — `tool_policy.require_owner_approval` lists only
   `Task` and `AskUserQuestion`.
10. **Add a `platform/` CI lane.** Absent because routing indexes the live `~/.claude`; `ROUTING_HOME`
    is the existing seam.

---

## 10. Limits of this unit

- **Un-reviewed single-agent output.** Condition 20 is FALSE *about this document*, which is the
  correct reading of `:11088-11090`, not modesty. The spec wants multiple independent synthesis agents
  then a meta-review of them; I am one, and this is the first Phase-14 artifact to exist.
- **7 of 21 conditions rest on sibling receipts I read but did not re-execute** (4-Linux-arm, 5, 6, 7,
  9, 11, 14). Marked per-row in the JSON.
- **NOT-CHECKED by me, never folded into a pass:** coverage % anywhere (this project has no
  `.coverage-thresholds.json`); the Linux suite; privacy and legality refuter lenses; a transcript
  read-ledger; the 2,007-unit catalog's schema conformance (I used two independent sibling scans).
- **Wrote nothing outside `command-center/`.** New paths: `PHASE14-SYNTHESIS.md`,
  `PROGRAM-STOPPING-SCORECARD.json`, `P14-MANIFEST-VERIFY.json`, `P14-CLOSE-VERIFY.json`,
  `P14-FLOORS.json`, plus `_p14_*` scratch probes and `_p14_suite_platform.log`. I ran no `git`
  mutation.

---
`SUCCESS:synthesis/phase14` — manifest verified on disk (1 of 14 entries MISMATCHED; the tree is
CI-red on `cc-render`), 21 of 21 stopping conditions scored **2 TRUE / 19 FALSE / 0 NOT-CHECKED**,
6-node root-cause hierarchy with an apex, 12-row decision trace, 7 failure modes meta-reviewed, and
4 of my own brief's 5 premises corrected by measurement.