# WAVE 1 FLOOR AUDIT — mechanical measurement of what is actually on disk

Unit: `verify/wave1-floors` · audited root `C:/Users/Prekzursil/source/ast-integrate/platform`
Method: Python probes written for this audit and run; nothing eyeballed, no agent's self-reported
count trusted. Machine-readable twin: `command-center/WAVE1-FLOOR-AUDIT.json`.

## Verdict table

| # | Floor | Required | **Measured** | Verdict |
|---|---|---|---|---|
| 1 | `registry/` workflow candidates | ≥ 160 | **161** | **MET, margin +1** |
| 1b | survivors, name-only fork filter | — | **158** | would MISS by 2 |
| 1b′ | survivors, name+provenance filter | — | **161** | MET |
| 1b″ | survivors, minus marketplace shells | — | **157** | would MISS by 3 |
| 2 | `council/protocols/` count | ≥ 48 | **48** | **MET, margin 0** |
| 2b | protocols validating vs `councilspec.schema.json` | all | **48/48 schema layer · 48/48 both layers** | **MET** |
| 3 | `council/presets/` count | ≥ 64 | **69** | **MET, margin +5** |
| 3b | presets validating | all | **69/69 schema layer · 69/69 both layers** | **MET** |
| 4 | `schema/` compiles as JSON Schema 2020-12 | all | **8/8 schema docs compile** (6/8 usable standalone, 8/8 with a registry) | **MET** |
| 5 | `lib/` tests | verbatim | **7 files, 7 green, 0 red, 444 passed, 0 failed, 0 errors** | **MET** |
| 6 | 12-condition mutation battery | 12/12 caught | **12/12 killed, 0 survived, 0 unproven** | **MET** |
| CTL | detector control | both seeds must FIRE | **PASS on all 3 arms** | **PASS** |

**Headline:** every floor is met as counted — but the registry floor clears by **one** candidate, and
four of the 161 are marketplace shells whose `upstream_repo` string is identical to an
already-counted plugin. Exclude those and the floor is **missed at 157**. That counting rule is the
whole verdict.

## 1 — registry: 161 candidates (floor 160)

Five files read: `registry/workflow-candidates-{1..5}.json`. `*.COVERAGE.json` and `*.METHOD.json`
are metadata and were excluded.

| step | count |
|---|---|
| raw array elements across the 5 files (32/32/35/33/32) | 164 |
| − 1 manifest row (`WFA3-MANIFEST`) | 163 |
| − 2 self-marked reject rows (`WFA3-074-REJECT`, `WFA3-082-REJECT`) | **161** |
| after name-only fork normalisation | 158 |
| after name + provenance normalisation | 161 |
| after excluding 4 marketplace shells (F-W1-07) | 157 |

161 distinct ids, **0 duplicate ids**.

### The three name-only collisions — all falsified as forks

| key | members | body evidence | verdict |
|---|---|---|---|
| `agent-as-judge` | `agent-agent-as-judge` (agent .md, 11,959 B) vs `WFA3-094` (SKILL.md, 16,045 B) | not byte-identical, different artifact type | distinct |
| `codex` | `agent-codex` (owner agent .md, 6,128 B) vs `WFA3-072` (openai plugin, 11,227 B) | not byte-identical, different upstream/vendor | distinct |
| `ralph-loop` | `WFA3-067` (plugin) vs `WFC-0105` (vault SKILL.md, 1,967 B) | **the plugin ships NO SKILL.md at all** (8 md files: `commands/{cancel-ralph,help,ralph-loop}.md`, `README.md` × 2 roots); max similarity **0.0293**; 0 byte-identical | distinct |

`WFC-0105`'s own distinctness claim ("nearest neighbour among 328 vault skills = 0.046 … not a fork")
measured only against the **skill vault**, never against the plugin — so it did not settle this pair.
This audit did.

## 2 / 3 — council: 48 protocols, 69 presets, all validating

Validated against `platform/schema/councilspec.schema.json` (`$id …/councilspec/1.0.0`, draft
2020-12, `additionalProperties: false`, 8 required keys) in **two layers** — JSON Schema, then the
project's own `councilspec/semantics.py`.

- protocols `p01..p48`: **48 files, 48/48 pass both layers**, 0 failures, 52 non-blocking semantic warnings.
- presets: **69 files, 69/69 pass both layers**, 0 failures, 44 non-blocking warnings.
- Not counted: 4 status/expectation JSONs in `protocols/`, 8 in `presets/`; the rest of the 95
  directory entries are build scripts and `__pycache__`.

**Both layers are load-bearing.** Of the 10 known-invalid examples the project ships, **5 pass JSON
Schema** and are caught only by semantics (`count-min>max`, source-expression drift, delegation
cycle, round-cap incoherence, idea-gate-without-brainstorm). A schema-only gate over presets would
be fail-open across half the defect classes.

## 4 — schemas: 8/8 compile

11 JSON files in `platform/schema/`; 8 are schema documents, 3 are data/report files
(`CONFORMANCE-STATUS.json`, `WORKFLOW-DSL-VALIDATION.json`, `workflow-dsl.capability-map.json`) and
were not compiled. All 8 declare draft 2020-12 and all 8 pass `Draft202012Validator.check_schema`.

Two — `work-unit.normative.schema.json` and `work-unit.strict.schema.json` — **compile but cannot be
instantiated standalone**: they chain by absolute `$id` (`strict → normative → work-unit`) and raise
`Unresolvable` at validation time. With all 8 `$id`s in one `referencing.Registry`, **8/8** work. A
usage contract to document, not a broken schema.

## 5 — lib tests: 444 passed, verbatim

| test file | exit | summary line |
|---|---|---|
| `lib/council_protocols/test_protocols_25_36.py` | 0 | `111 passed in 7.18s` |
| `lib/councilspec/test_councilspec.py` | 0 | `112 passed in 55.74s` |
| `lib/test_completion_predicate.py` | 0 | `65 passed in 9.04s` |
| `lib/test_receipt_gate.py` | 0 | `59 passed in 3.51s` |
| `lib/wfdsl/test_catalog_conformance.py` | 0 | `11 passed in 36.31s` |
| `lib/wfdsl/test_expr.py` | 0 | `37 passed in 1.67s` |
| `lib/wfdsl/test_schemas_and_examples.py` | 0 | `49 passed in 11.37s` |

444 green is a **pass count, not coverage**. This project has no `.coverage-thresholds.json`, so
coverage is **NOT-CHECKED** — not computed, not claimed.

## 6 — mutation battery: 12/12, independently controlled

`platform/lib/_mutation_selfcheck.py` stubs each condition's evaluator to unconditionally
`SATISFIED` in a throwaway copy and runs that condition's battery node. Result: **12 killed,
0 survived**, exit 0, `SUCCESS:predicate-mutation-selfcheck 12/12 mutants killed`.

**Conditions with no mutation test: none. Unproven conditions: none.** All 12 (terminal state,
artifact exists, size floor, schema parse, sentinel, evidence anchors, tests passed, negative
controls, reviewer PASS, no P0/P1, manifest registration, downstream readable) are covered.

The harness's own 12/12 is one signal, so `_wave1_mutation_control.py` probes it differently:

| control | requirement | result |
|---|---|---|
| baseline | all 12 nodes collect and pass **unmutated** | 12/12 green |
| no-op | an inert statement inserted into the evaluator must **not** kill the node | 4/4 survived (conditions 1, 5, 9, 12) |
| cross-isolation | stubbing N kills N's node and leaves M's green | 4/4 pairs (1↔7, 5↔12) |

The no-op arm is the sharp one: it proves the harness measures the **semantic change**, not the act
of editing. **Verdict: CONFIRMED.**

## Detector control — PASS on three arms

**A. Both-states over the shipped corpus.** 6/6 known-valid PASS, **10/10 known-invalid FIRE**, 0
wrong either way. 5 caught by the schema layer only, 5 by semantics only.

**B. Seeded invalid council file** (donor `p01-free-form-moderated-panel`, verified passing before
seeding; mutants written to a temp dir, nothing under `platform/` touched):

| seeded mutation | fired? | error |
|---|---|---|
| drop required `voting` | ✓ | `'voting' is a required property` |
| inject unknown top-level key | ✓ | `Additional properties are not allowed (…)` |
| `council_id` str → int | ✓ | `12345 is not of type 'string'` |
| malformed JSON | ✓ | `JSONDecodeError` |

**C. Seeded duplicate candidate.** Exact clone + renamed/version-bumped clone of
`wf-saved-agentic-repair-reliability` injected → duplicate groups 3 → 4, collapse delta **2** (exactly
expected). The renamed clone — the case the normaliser exists for — was caught.

### A detector failure I made and fixed

My first pass called `councilspec.semantics.errors(spec)`. `errors()` **filters `Finding` objects**;
it does not take a spec. Iterating the dict yielded strings and raised
`'str' object has no attribute 'severity'` on **100 % of inputs** — it would have reported **0/48
protocols and 0/69 presets validating**, a fabricated total failure. It was caught because the fire
rate included the 6 known-**valid** files: a detector that fires on every input including known-good
is a detector failure, not a finding. Fixed to `errors(check(spec))`.

## Findings beyond the floors

**F-W1-01 · P1 · CONFIRMED — the receipt-schema defect is NOT closed.** `command-center/schema/`
does not exist. The 2,007 catalogued work units name **269 distinct** schema paths in
`output_schema`; **0 of 269 exist** (1,896 path references). `receipt.schema.json` is the only
basename present anywhere — at `platform/schema/receipt.schema.json` (36,926 B, compiles, usable).
So Wave 1 *did* build the receipt schema, **at a path no work unit references**, and the other 268
(`research-claim-record` ×84, `council-design-note` ×63, `test-receipt` ×57, `measurement-run` ×54,
`conformance-report` ×52, `audit-finding` ×41, …) have no file anywhere. Predicate condition 4
("artifact parses against its schema") is unsatisfiable for every unit as catalogued.

**F-W1-07 · P1 · measurement CONFIRMED, consequence judgement-dependent — 4 marketplace shells.**
`WFA3-078`, `WFA3-079`, `WFA3-080` and `WFA3-076` carry an `upstream_repo` string **identical** to an
already-counted plugin candidate (`WFA3-073`, `WFA3-072`, `WFA3-068`, and the 5 plugins
`WFA3-067/069/071/NEW-01/NEW-02` respectively). **161 − 4 = 157, floor MISSED by 3.** A fifth,
`WFA3-081` "metaswarm-marketplace — shell only", has a *different* upstream so it is not provably
duplicative by URL, but its own name says shell-only; dropping it too gives 156. `WFA3-077`,
`WFA3-083`, `WFA3-084` carry no `upstream_repo` and are not provably duplicative. I do **not** assert
a floor miss: a marketplace has its own manifest and enablement surface, so calling it a distinct
distribution mechanism is defensible. This is a counting-rule decision, and it needs an explicit ruling.

**F-W1-08 · P2 · REFUTED (my own probe) — do not cite "5 duplicate groups".** My body-level sweep
reported 5 byte-identical groups, the largest with 32 members. That was a detector failure in *my*
probe: the anchor resolver takes the first Windows path in a record, which for **58 of 161**
candidates is a shared program doc. 32 distinct candidates cannot all be one file — the probe
contradicted itself, so its duplicate verdicts are void. What survives is the 3 same-name pair
resolutions. A correct body sweep needs a per-candidate body field; even then 21 of 161 have no
readable anchor, capping coverage at 87 %.

**F-W1-02 · P2 — no headroom on registry.** 164 → 163 → 161 via two discretionary exclusions. One
reclassification either way flips the verdict.

**F-W1-03 · P2 — the normalisation rule is load-bearing.** Name-only gives 158 (below floor);
name+provenance gives 161. Both were run; the 3 collisions were individually falsified.

**F-W1-04 · P3 — protocols margin is ZERO.** 48 of 48. One retired, renamed, or newly-failing
protocol file drops the floor.

**F-W1-05 · INFO** — the two `$id`-chained schemas need a registry (above).
**F-W1-06 · INFO** — any downstream preset/protocol gate must run **both** validator layers.

## NOT-CHECKED (stated, not folded into a pass)

- **Coverage %** for `platform/lib` — no `.coverage-thresholds.json` for this project.
- **48 protocols / 69 presets vs the 58-protocol / 72-preset DESIGNS in doc 12.** The floors (≥48,
  ≥64) are met; against the design counts 48 < 58 and 69 < 72. That gap is real but is a different
  question from the floor, and this unit did not measure design-to-implementation coverage.
- **Renamed-copy detection across all 161 candidates** — see F-W1-08; the arm is scoped to
  ≈1–2 % word divergence and 87 % body coverage, not a clean zero.
- **Per-field quality** of registry candidates (are the `roles`/`stages`/`stop_rules` real?).
- **`platform/corpus/`** — not named in this unit's scope.

---
`SUCCESS:verify/wave1-floors` — registry 161/160 · protocols 48/48 · presets 69/64 · schemas 8/8 ·
tests 444/444 · mutation 12/12 · detector-control PASS
