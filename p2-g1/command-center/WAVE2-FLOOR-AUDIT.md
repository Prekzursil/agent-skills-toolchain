# WAVE-2 FLOOR AUDIT — `verify/wave2-floors`

**Method:** every number below was read off disk by
`command-center/_wave2_floor_audit{,2,3,4,5}.py`. No agent's self-reported count was accepted.
Machine-readable twin: `command-center/WAVE2-FLOOR-AUDIT.json`.

**Repo state at audit time:** `main` @ `edcf9f5b`, 618 dirty/untracked entries.

---

## Headline

**5 of 6 floors MET, 1 PARTIAL, zero test regression — but the entire wave is uncommitted.**

| # | Floor | Measured | Verdict |
|---|---|---|---|
| 1 | blueprints >= 96 | **97** top-level (103 blueprint-shaped docs), 103/103 schema-valid, 0 semantic violations | **MET** (caveat below) |
| 2 | flagship w/ e2e tests >= 40 | **65** declared flagship, 65/65 have a dedicated test file, `1111 passed` | **MET** |
| 3 | 9 architectures + tournament verdict | **9** + `TOURNAMENT-VERDICT.md` (40,120 B), minority report present | **MET** |
| 4 | `scout.py` / `forge.py` executable, forge can REJECT | both ran; forge REJECTED **and** CERTIFIED | **MET** |
| 5 | substrate: `output_schema` paths resolve | `command-center/schema/` now exists, 233 files, **233/233** cc-schema tokens resolve; **36** tokens still unresolved | **PARTIAL** |
| 6 | no test regression vs Wave 1's 444/444 | **444 passed** on the exact Wave-1 module set; full suite **2767 passed, 14 skipped, 0 failed** | **MET — ZERO REGRESSION** |

---

## Detector control (mandatory) — CONFIRMED, with one disclosed blind spot

Seeded four controls into a scratch copy of `platform/workflows/` and re-ran the same validator:

| control | seeded defect | fired? |
|---|---|---|
| A | `dsl_version: 99` (wrong type), `stages` kept | **YES** — `dsl_version: [type] 99 is not of type 'string'` |
| B | `stages: [{"nonsense_key": true}]` | **YES** — 3 errors incl. `'id' is a required property`, `unevaluatedProperties` |
| C | required `stages` removed | **NO — blind spot, see below** |
| D | exact-mechanism clone under a new id/name/description | **YES** — clustered with `bp-cnc-01-five-persona-design-council` |
| + | positive control: untouched original | **still passes** (silent where it should be silent) |

**Control C is a real weakness in MY classifier, disclosed rather than hidden.** A doc that loses
its `stages` key stops matching the blueprint heuristic and is filed as a *report* file, so it
leaves the denominator instead of failing. The DSL validator itself rejects it correctly
(`<root>: [required] 'stages' is a required property`) when the classifier is bypassed. So the
blind spot is in the audit's file-classification step, not in the shipped schema.

**Pass 1 of this audit reported the control REFUTED** — because my own control-C seeding created
exactly that reclassification, so the invalid file never reached the validator. Recorded, not
deleted (`detector_control.C_KNOWN_BLIND_SPOT`).

**Residual check the blind spot demands — it did NOT bite.** If a report-classified file were
really a blueprint that lost a required field, it would vanish from the denominator silently. I
checked all 24: **0** of them carry `dsl_version`, `stages`, or 4+ blueprint keys
(`_wave2_blindspot_check.py`). So the 97 is not inflated by a hidden drop-out.

**The 97 has three mechanically independent signals**, which is why I state it as a count rather
than an estimate: my recursive classifier (97), `scout population` -> `executable_dsl_blueprints: 97`
(a different code path in `foundry/registry.py`), and a non-recursive glob keyed only on
`{dsl_version, stages}` (97). 115 top-level JSON files = 97 blueprints + 18 reports; plus 2 `.md`
status files, `_shared/` (2 subworkflows) and `forged/` (4 forge outputs + 6 reports) below.

Two further self-inflicted detector failures in pass 4, both corrected in pass 5 and both recorded:

- `completion_sentinel` check used `id in sentinel` and returned **0**. The shipped rule SEM-002
  (`platform/lib/wfdsl/semantics.py:85-99`) requires the literal `SUCCESS:<own-id>`. Mine was a
  *weaker* question, so its 0 was never a refutation of SEM-002's **96**. Real value: **96**.
- `assigned_model_vendor_role` polarity was **inverted** — pass 4 called the 1,879 canonical
  object-form units non-canonical. `platform/schema/work-unit.schema.json` states the object form
  (1,879) is canonical and the slash-triple string (128) is the odd shape. Real value: **128**.

---

## 1. Blueprints — 97 top-level, floor 96 MET

`platform/workflows/` holds 127 JSON files: **103** blueprint-shaped docs and **24**
STATUS/VALIDATION report files. The 103 split as:

- **97 top-level blueprints** — the floor set
- 2 shared subworkflows (`_shared/shared.pairwise-overlap-matrix`, `shared.write-as-you-go-artifact`)
- 4 forge outputs (`forged/`)

**Validation: 103/103 pass `platform/schema/workflow-dsl.schema.json`** with **0** semantic-rule
violations. No unparseable files. No duplicate ids among the 97.

Independent corroboration: `scout population` reports `executable_dsl_blueprints: 97` — a
different code path arriving at the same 97.

### Material distinctness — 97/97, but carried by ONE axis

Normalising by mechanism (stage topology + roles + gates + stopping rule), **name-independently**,
all **97/97 are distinct** and there are **zero exact-mechanism duplicate clusters** among them.

That conjunction is doing almost all its work on a single axis:

| axis | distinct values across 97 | clusters | blueprints sitting in a cluster |
|---|---|---|---|
| **stages** | **97** | 0 | 0 |
| roles | 32 | 16 | 81 |
| gates | 43 | 22 | 76 |
| **stopping_rules** | **2** | 2 | 97 |

The two stopping-rule clusters are 55 and 42 blueprints wide — i.e. every blueprint in the library
uses one of two normalised stopping shapes. Largest role cluster: 13
(`both-states-detector-control`, `bp-arc-04.failure-domain-mapping-workshop`,
`crv.differential-change-review-with-history`, `crv.refactor-equivalence-proof`,
`firing-path-revalidation`, `measurement-instrument-validation`,
`memory-temporal-validity-curation`, `orphaned-run-recovery-from-disk`,
`scanner-detector-integrity-probe`, `shared-grounding-pack-emission`,
`tst.fail-first-red-proof-certification`, `tst.smallest-check-ladder`, `tst.ui-invariant-walk`).
Largest gate cluster: 10.

**5 pairs are identical on 3 of the 4 axes** and differ only in stage topology:

| pair | identical axes |
|---|---|
| `bp-arc-04.failure-domain-mapping-workshop` / `orphaned-run-recovery-from-disk` | roles, gates, stopping |
| `cheap-tier-first-campaign` / `remote-fleet-propose-only` | roles, gates, stopping |
| `firing-path-revalidation` / `measurement-instrument-validation` | roles, gates, stopping |
| `license-and-rights-governance-register` / `live-estate-incident-triage` | roles, gates, stopping |
| `revert-gate-rollback-drill` / `stale-mega-pr-reconcile` | roles, gates, stopping |

The one exact-mechanism duplicate cluster in the whole tree is two **forge outputs**:
`forged/fused.cnc07-arc05.workflow.json` and `forged/fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json`
— expected, since the tournament winner *is* the fusion.

**Honest reading: the raw count (97) and the distinct count (97) agree, but "materially distinct"
is an overclaim if read as distinct on all four axes. It is distinct on stage topology; on roles,
gates and stopping rules the library is heavily templated.**

---

## 2. Flagship blueprints with real tests — 65, floor 40 MET

**65** of the 97 blueprints carry `flagship: true`. All **65** have a dedicated test file in
`platform/lib/workflows/` (75 test files present):

- **52** match on the exact derived filename (`bp-cnc-01-...` -> `test_bp_cnc_01_....py`)
- **13** match via the short-name convention the repo actually uses
  (`bp-arc-01.architecture-tournament` -> `test_bp_arc_01.py`, the 5 `bp-arc-*`, 4 `bp-pln-*`,
  3 `bp-req-*`, and `two-track-ui-audit-rubric-verdict` -> `test_two_track_ui_audit.py`)
- **0** flagship blueprints with no test at all

**Verbatim run** (`cd platform/lib && python -m pytest -q --no-header <65 flagship test files>`):

```
1111 passed in 20.18s
```

exit code 0, zero failures, zero skips.

---

## 3. Architecture tournament — 9 + verdict, minority report PRESENT

`platform/architecture/` holds exactly **9** architecture documents — `config-first`,
`cross-vendor`, `distributed-runtime`, `gateway-lazy`, `generated-ssot`, `marketplace-first`,
`maximal-hybrid`, `security-first`, `ux-product-first` — plus **`TOURNAMENT-VERDICT.md`** (40,120
bytes). All 9 are named in the verdict (6–17 mentions each); none was silently dropped.

**Dissent was NOT dropped.** The verdict carries a first-class minority section:

- `TOURNAMENT-VERDICT.md:219` — `## 4. MINORITY REPORT — what the winner gives up, and who held the better answer`
- `:221` — *"The spec requires preserved dissent. A unanimous verdict here would be a panel failure"*
- 10 occurrences of `dissent`, 2 of `minority report`
- named dissents **M1–M5** are carried forward into the migration gate table as concrete work
  items: `G2` (M4 dissent, the `or ""` coercion), `G7` (M3, 601-unit force-promotion),
  `G9` (M5, generated-ssot Phase 1-2), `G10` (M1, marketplace Stage 0 + `mkt-profile` gate)
- `:435` — an explicit `[A-only]` list of *"claims the panel did NOT re-verify, each load-bearing
  for a minority-report item"*

One thing the doc flags about itself, worth surfacing: `:366` notes §7.4 is titled *"Three lesser
objections, **answered rather than conceded**"* — i.e. the verdict itself marks that section as
the one place dissent was argued down rather than preserved.

---

## 4. `scout.py` and `forge.py` — both RUN; forge can REJECT and CERTIFY

### scout

```
$ python -m foundry.scout population            # cwd: platform/lib
{ "total": 260, "registry_rows": 163, "executable_dsl_blueprints": 97, ... }
SUCCESS:scout-population
```

```
$ python -m foundry.scout search --goal-text "audit a wide agent fan-out for detector failures
    and refute overclaims" --require stages --require barriers --require stopping_rules
    --hazard detector-silent-in-both-states --top 5
population: 260 candidates (163 registry rows + 97 executable DSL)
input_fingerprint: 9ab01c394404ad83
rank   score   capW   capR    lex    haz  deriv       id
   1   0.541   1.00   1.00   0.26   0.00  structural  bp-res-05-briefed-fact-reprobe-council
   2   0.541   1.00   1.00   0.26   0.00  declared    wf-saved-agentic-repair-reliability
   3   0.484   1.00   1.00   0.10   0.00  structural  two-track-ui-audit-rubric-verdict
   4   0.482   0.49   0.67   0.17   1.00  structural  bp-arc-03.anti-overfit-architecture-audit
        missing: ['barriers']
   5   0.480   1.00   1.00   0.08   0.00  structural  worktree-isolated-parallel-build
recommendation: ADOPT-WITH-WRAPPER   ({'ADOPT-WITH-WRAPPER': 3, 'MERGE': 3})
SUCCESS:scout-search
```

Scout also *refuses* a malformed goal rather than guessing — a bogus capability id yields
`FAILED:scout-search goal is not well-formed`, naming the offending id.

### forge — the gate fires in BOTH directions

`REJECTED` is reachable (`--strategy union`, verbatim):

```
axis               base    donor    fused   delta vs best source
correctness      1.0000   1.0000   1.0000   +0.0000
coverage         0.7375   0.7619   0.8667   +0.1048
recovery         0.8333   0.8333   0.9167   +0.0834
usability        1.0000   1.0000   1.0000   +0.0000
DSL gate: schema_valid=True semantic_violations=0
decomposition roundtrip: CONFIRMED

VERDICT: REJECTED
  - gratuitous-cost: 9 grafted stage(s) [...] change NO axis when ablated - the fusion carries
    them for free. Per spec :11282 a merged workflow is not accepted because it contains more
    stages, so a stage that measures nothing must not ride along
SUCCESS:forge-fuse REJECTED (the gate fired; this is a working gate, not an error)
```

`CERTIFIED` is also reachable — so it is not an always-reject gate either (`forge tournament`):

```
strategy             verdict     stages  delta  gratis  improvements
stage-splice         CERTIFIED        9     -1       0  coverage +0.1048, recovery +0.0833
common-core          REJECTED        17     +7       9  coverage +0.0381, recovery +0.0833
union                REJECTED        18     +8       9  coverage +0.1048, recovery +0.0833
best-of-breed        CERTIFIED        9     -1       0  coverage +0.1048, recovery +0.0833
conditional-hybrid   CERTIFIED        9     -1       0  coverage +0.1048, recovery +0.0833
ensemble             CERTIFIED        9     -1       0  coverage +0.1048, recovery +0.0833
progressive          CERTIFIED        9     -1       0  coverage +0.1048, recovery +0.0833
WINNER: best-of-breed
SUCCESS:forge-tournament
```

**5 of 7 strategies CERTIFIED, 2 REJECTED on the same input pair.** Both-states proven: forge is
neither a no-op that always fuses nor a gate that always refuses.

---

## 5. Substrate — the P1 is largely closed; PARTIAL

`command-center/schema/` **now exists** with **233** JSON schema files. The pinned P1 was
"0 of the 269 distinct paths resolve".

| measurement | value |
|---|---|
| work units | 2,007 |
| distinct `output_schema` **values** | 367 |
| ... of which are prose, not a bare path | 135 |
| distinct path **tokens** extracted | 272 |
| tokens resolving on disk | **236** |
| tokens NOT resolving | **36** |
| `command-center/schema/*` tokens | **233/233 resolve**, 1,859 references |
| units whose `output_schema` is loadable (exists AND parses) | **1,947 / 2,007** |

**The 36 unresolved tokens are entirely outside the `command-center/schema/` namespace:**
20 × `tools/marketplace/schema/*`, 14 × `tools/plugin/schema/*`, 2 × `.claude-plugin/*`
(37 references total). **Neither `tools/marketplace` nor `tools/plugin` exists as a directory** —
`tools/` exists with 20+ other subdirectories, but not those two. These are schemas the
marketplace/plugin units would author; Wave 2 did not create that tree.

**Reconciliation note (UNVERIFIED premise in the pinned brief):** I cannot reproduce
"269 distinct paths / 1,896 references" under any definition this script computes — I get 272
tokens / 2,007 references, or 233 cc-schema tokens / 1,859 references. The *direction* is
unambiguous either way (0 resolving -> 236/272). The experiment that would settle the exact
denominator is to recover the original counting script from the Wave-1 substrate probe
(`platform/lib/_probe_substrate_*.py`); I did not run it.

---

## 6. Full platform test suite — ZERO REGRESSION

Full suite, verbatim (`cd platform/lib && python -m pytest . -q --no-header`):

```
2767 passed, 14 skipped in 135.48s (0:02:15)
```

**The load-bearing number — the Wave-1 baseline re-run.** Wave 1's 444/444 was the exact module
set `wfdsl + councilspec + council_protocols + test_completion_predicate.py +
test_receipt_schema_gate.py`. Re-running precisely that set:

```
444 passed in 77.90s (0:01:17)
```

**Exactly 444, zero failures. No regression.** Per-module composition still matches Wave 1 term
for term:

| module | tests |
|---|---|
| `wfdsl` | 97 |
| `councilspec` | 112 |
| `council_protocols` | 111 |
| `test_completion_predicate.py` | 65 |
| `test_receipt_schema_gate.py` | 59 |
| **Wave-1 subtotal** | **444** |
| `test_schema_resolver.py` (new) | 31 |
| `foundry` (new) | 147 |
| `workflows` (new) | 2145 passed, 14 skipped |

**The 14 skips are not hidden failures.** All are conditional per-blueprint parametrised skips in
`test_bp1_blueprint_conformance.py`: 11 × `"<id> declares no secret param"` (line 286) and
3 × `"<id> has no fanout stage"` (line 346).

---

## Open defects found by this audit

### P1 — `WAVE2-UNCOMMITTED`: none of Wave 2 is in git

| directory | files on disk | git-tracked |
|---|---|---|
| `platform/workflows` | 129 | **0** |
| `platform/architecture` | 103 | **0** |
| `platform/lib/workflows` | 134 | **0** |
| `platform/lib/foundry` | 13 | **0** |
| `command-center/schema` | 233 | **0** |
| **total** | **612** | **0** |

Wave 1 by contrast is tracked (`platform/lib/wfdsl` 17/17, `councilspec` 10/10,
`council_protocols` 7/7, `platform/council` 164, `platform/schema` 32 tracked + 11 dirty).

`git clean -xfd`, a `checkout`, or a worktree reset destroys the entire wave. I did not commit —
the orchestrator owns commits (~20 agents share one index).

### P2 — `FORGED-ID-COLLISION`

Three files in `platform/workflows/forged/` carry the **identical** id `fused.dc5b5f0b10f7`:

| file | stages |
|---|---|
| `fused.cnc07-arc05.workflow.json` | 9 |
| `fused.cnc07-arc05.TOURNAMENT-WINNER.workflow.json` | 9 |
| `REJECTED.union.cnc07-arc05.workflow.json` | **18** |

A loader keyed on workflow id cannot distinguish the **REJECTED** 18-stage union from the
**CERTIFIED** 9-stage fusion. The `REJECTED.` filename prefix is the only discriminator, and it
lives outside the document.

### P2 — `STOPPING-RULE-BOILERPLATE`

`stopping_rules` take **2** distinct normalised values across all 97 blueprints. The spec's
"distinct by ... stopping rule" axis therefore contributes essentially no discrimination, and the
97/97 distinctness figure rests on stage topology alone. See §1.

### P3 — `FORGE-COST-LABEL`

`forge fuse` prints `cost (NOT an axis): {'stage_count': 8, ...}`. That value is
`certification.cost_delta_vs_largest_source` (18 − 10 = 8), but the label says only "cost", while
`certification.fused.cost.stage_count` is **18**. An unlabelled delta reads as an absolute; a
reader can conclude the union shrank the workflow when it grew it by 8 stages. The `tournament`
sub-command labels the same quantity correctly (`delta` column).

### INFO — `CATALOG-DEFECTS-UNMOVED`

Four of five pinned catalog defects are unchanged. Wave 2 closed the schema substrate but did not
touch catalog conformance.

| defect | pinned | now |
|---|---|---|
| `output_schema` refs failing the schema pattern | 159 | **159** |
| unresolvable dependency refs | 41 | **41** (SEM-001 reports 40; ±1 definitional) |
| completion sentinels not naming own unit (SEM-002) | 96 | **96** |
| non-canonical `assigned_model_vendor_role` (string-triple form) | 128 | **128** |
| `output_schema` unloadable (token missing or unparseable) | — (0 of 269 resolved) | **60 of 2,007** — improved |

Profile pass rates identical to the pinned figures: **structural 2007/2007 · normative 1790/2007 ·
strict 1679/2007** (`strict_only_count: 111`, `cascade_from_normative: 217`).

The unresolvable dependency refs are bucket-prefix tokens, not unit ids — e.g. `TST-0001` depends
on `CC` and `IMP`, `TST-0033` on `ARC`. The pattern suggests a family/bucket abbreviation that was
never added to the `Bnn` bucket vocabulary SEM-001 accepts.

---

## Artifacts

- `command-center/WAVE2-FLOOR-AUDIT.json` — machine-readable, per-file detail for all 103 docs
- `command-center/_wave2_floor_audit.py` — pass 1: classification, schema validation, mechanism fingerprinting
- `command-center/_wave2_floor_audit2.py` — pass 2: fixed detector control, prose-aware substrate resolution
- `command-center/_wave2_floor_audit3.py` — pass 3: distinctness on the real 97, flagship pytest, substrate reconcile
- `command-center/_wave2_floor_audit4.py` — pass 4: catalog deltas, git census, forge id collision
- `command-center/_wave2_floor_audit5.py` — pass 5: corrected two inverted pass-4 detectors, stamped verdicts
- `command-center/_wave2_blindspot_check.py` — residual check on the disclosed classifier blind spot + third independent blueprint count
- `command-center/_wave2_catalog_conf.json` — raw catalog conformance report
