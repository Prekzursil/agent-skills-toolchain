# Council presets 33-48 — editing guide (lane 3)

Sixteen editable CouncilSpec instances for design cards **C-D33 … C-D45** and **C-X46 … C-X48**
from `12-COUNCIL-PROTOCOLS-AND-PRESETS.md`. Every file validates against
`platform/schema/councilspec.schema.json` **and** all 12 semantic rules in
`platform/lib/councilspec/semantics.py`.

> This directory is shared with the other three preset lanes. Only files named `C-D33-*` …
> `C-D45-*`, `C-X46-*`, `C-X47-*`, `C-X48-*` belong to this lane.

## Validate after every edit

```bash
cd platform/lib && python -m councilspec ../council/presets/<file>.councilspec.json
```

Prints `OK` or `REJECTED` with the schema and semantic errors, then a terminal
`SUCCESS:councilspec-validate` / `FAILED:councilspec-validate`. To re-verify the whole lane
(baseline + mutation battery + dial-pointer resolution + coverage):

```bash
python platform/council/presets/_probe_preset_validation.py     # writes LANE-3-PRESET-VALIDATION.json
```

## The files

| # | file | preset | seats | binding intent |
|---|---|---|---|---|
| 33 | `C-D33-harness-apply-gate-10` | release_readiness_board | 10 | binding, two-key, owner in the loop |
| 34 | `C-D34-merge-adjudication-12` | code_review_tribunal | 12 | binding |
| 35 | `C-D35-scenario-planning-9` | product_strategy_council | 9 | advisory |
| 36 | `C-D36-prediction-tournament-12` | forecasting_council | 12 | shadow (cannot decide by construction) |
| 37 | `C-D37-morphological-12` | requirements_council | 12 | advisory — the only preset that may claim COMPLETENESS |
| 38 | `C-D38-triz-8` | innovation_moonshot_council | 8 | advisory, 45 min, one inventive round |
| 39 | `C-D39-team-b-10` | risk_committee | 10 | advisory, 2x cost, one claim per program |
| 40 | `C-D40-adversarial-collab-8` | adversarial_collaboration | 8 | advisory — remedy for IRREDUCIBLE_DISAGREEMENT |
| 41 | `C-D41-argument-map-10` | custom (← root_cause_council) | 10 | advisory — for a decision re-litigated twice |
| 42 | `C-D42-evidence-clerk-10` | evidence_adjudication_jury | 10 | advisory — never on an ideation lens |
| 43 | `C-D43-nested-subcouncils-15` | general_purpose_auto_composed | 15 | advisory — the auto-composed default entry point |
| 44 | `C-D44-crossvendor-mirrored-12` | benchmark_results_jury | 12 | advisory, 2x cost, entropy-scored |
| 45 | `C-D45-jury-12-plus-judge` | ethics_legal_board | 13 | binding, unanimity else hung |
| 46 | `C-X46-gem-hunt-40lens` | custom (← hundred_idea_brainstorm) | 43 | advisory, discovery only |
| 47 | `C-X47-discovery-swarm-64` | hundred_idea_brainstorm | 64 | advisory — the spec's 100-idea rule, verbatim |
| 48 | `C-X48-brainwriting-36` | custom (← hundred_idea_brainstorm) | 36 | advisory |

`preset` is itself a dial. Three files declare `custom` with `extends_preset` naming the family
they were forked from, because forcing a required-preset label onto them would have been a
mislabel — each says so in its own `metadata.notes` under `PRESET-NAME`.

## How a preset documents itself

JSON has no comments, and the schema sets `additionalProperties: false` everywhere, so a `//`
comment or a `_comment` key would make the file **invalid**. Documentation therefore lives in the
fields the schema actually provides:

| channel | carries |
|---|---|
| `metadata.notes` | WHEN TO USE / WHEN NOT TO USE, the `EDITABLE DIALS` list as JSON Pointers, the human-readable stopping rule, and any caveat |
| `metadata.spec_citations`, `metadata.lineage` | design-card and protocol provenance |
| `objective.charter` | why the protocol is shaped this way |
| `objective.success_criteria` | the design card's stopping conditions in prose |
| `note` on each stopping leaf | what that dial means, what breaks if you move it |
| `producer` on each `custom:` leaf | what computes the metric — the anti-fabrication control |
| `participant.context.briefing` | the instruction that makes a seat behave like its role |
| `topology.committees[].mandate` | what a committee is for |

Every JSON Pointer named in an `EDITABLE DIALS` list is **machine-checked** to resolve in that
file (`_probe_preset_validation.py`, check 4 — 77 pointers currently). Prose that names a dial
which does not exist fails the probe.

## Two substrate constraints you will hit when editing

**1. `stopping.source_expression` is mutually exclusive with per-dial documentation.**
SEM-001 requires `source_expression` to parse to a tree *identical* to `stopping.expression`, and
the reference parser emits neither `note` nor `producer`. So a leaf carrying either key makes
SEM-001 fail. Proven in both states, with controls, by `_probe_sem_rule_collision.py`:

| case | fixture | result |
|---|---|---|
| A | `producer` + `source_expression` | SEM-001 ERROR |
| B | no `producer` + `source_expression` | ok, SEM-012 WARN |
| C | `producer`, no `source_expression` | clean ← what 15 files do |
| D | `note` + `source_expression` | SEM-001 ERROR |
| E | same as D minus `note` | clean ← isolates `note` as D's cause |

Fifteen files keep the per-dial notes and put the human form in `metadata.notes` as
`STOPPING (human form): …`. **`C-X47` alone takes the opposite trade** — it declares
`source_expression` (the spec quotes that rule verbatim) and therefore has no leaf notes. If you
edit C-X47's stopping rule, change the string *and* the tree together or the validator will
reject the file. That rejection is intended behaviour, not a bug.

**2. `producer` and `value_type` exist ONLY on a `custom:` leaf.**
Adding either to a registry metric (`executable_test_settled`, `coverage_score`, …) makes the leaf
match none of the four `stop_leaf` branches and the file is rejected with a whole-subtree
"is not valid under any of the given schemas" message that does not name the offending key.

## Known defects reported, not inherited

- **C-X46 seat arithmetic.** The design card says `seats: 40` while its own role list
  (`lens_seat_x40,ground_agent,synthesiser_x2`) sums to **43**, and its note records
  "measured 43 agents". `exact_n` is 43 here; the 40 is read as the lens-seat count only. This is
  the only such mismatch in the slice — checked mechanically over all 16 cards, with a detector
  control, by `_probe_seat_arithmetic.py`.
- **Outcome vocabulary is lossy.** The design cards distinguish `DEFER` from
  `INSUFFICIENT_EVIDENCE`; `outcomes.allowed` has only `no_decision` for both, so the distinction
  must be carried in the receipt.
- **`receipt_schema` path conflict.** Files point at `platform/schema/receipt.schema.json`, which
  exists. The catalog's work units still point at `command-center/schema/receipt.schema.json`,
  which does not. Unresolved upstream; the field is a documented string, not a resolved `$ref`.
- **Group structure needs an explicit roster.** `topology.committees` / `caucuses` reference
  `participant_id`s, so an auto-composed swarm cannot express grouping there. C-X48's 6 groups of
  6 live in the protocol stage, where no validator checks them.
- **Nesting depth is unenforced.** `topology.subcouncils` recurses into the full CouncilSpec with
  no depth limit, so the design's "one level only" rule is documentation plus an owner gate in
  C-D43, not validation.

## Files in this lane

16 × `*.councilspec.json` · `_probe_preset_validation.py` · `_probe_sem_rule_collision.py` ·
`_probe_seat_arithmetic.py` · `LANE-3-PRESET-VALIDATION.json` · this README.
