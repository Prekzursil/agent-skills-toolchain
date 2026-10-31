---
title: README-LANE-2
type: note
permalink: dqverify-repo-20261013/platform/council/presets/readme-lane-2
---

# Council presets, design indices 17-32 (lane 2) — editing guide

17 files. Every one is plain JSON, validates standalone against
`platform/schema/councilspec.schema.json`, and needs no build step to consume.

Each file carries its own editing guide in `metadata.notes` (an `EDITABLE DIALS`
section naming each dial by JSON pointer). This README is the cross-file table.
JSON has no comments and the CouncilSpec schema is closed (`additionalProperties:
false`) at every level, so `metadata.notes` plus per-leaf `note` fields on stage
`exit_when` expressions are the only in-file documentation channels the contract
allows. Both are used.

## The files

| idx | file (`*.councilspec.json`) | `preset` archetype | seats | design card |
|----:|---|---|----:|---|
| 17 | `c-s17-red-blue-4` | `security_red_blue_council` | 5 | C-S17 red-blue-4 |
| 18 | `c-s18-oxford-4-plus-judge` | `custom` | 5 | C-S18 oxford-4-plus-judge |
| 19 | `c-s19-socratic-chair-plus-4` | `requirements_council` | 5 | C-S19 socratic-chair-plus-4 |
| 20 | `c-s20-charrette-5-design` | `custom` | 5 | C-S20 charrette-5-design |
| 21 | `c-s21-six-hats-6` | `custom` | 6 | C-S21 six-hats-6 |
| 22 | `c-s22-nominal-group-6` | `custom` | 7 | C-S22 nominal-group-6 |
| 23 | `c-s23-delphi-5-anon-3rounds` | `custom` | 6 | C-S23 delphi-5-anon-3rounds |
| 24 | `c-s24-ach-5-hypotheses` | `root_cause_council` | 5 | C-S24 ach-5-hypotheses |
| 25 | `c-s25-war-room-5-incident` | `incident_war_room` | 5 | C-S25 war-room-5-incident |
| 26 | `c-s26-postmortem-5-blameless` | `postmortem_council` | 5 | C-S26 postmortem-5-blameless |
| 27 | `c-s27-kill-the-company-5` | `risk_committee` | 5 | C-S27 kill-the-company-5 |
| 28 | `c-s28-stakeholder-negotiation-5` | `negotiation_council` | 5 | C-S28 stakeholder-negotiation-5 |
| 29 | `c-s29-two-key-authorization` | `custom` | 2 | C-S29 two-key-authorization |
| 30 | `c-s30-rfc-last-call-open` | `custom` | 6 | C-S30 rfc-last-call-open |
| 31 | `c-d31-deep-architecture-12` | `architecture_review_board` | 13 (4 meta + 3x3) | C-D31 deep-architecture-12 |
| 32 | `c-d32-deep-security-threat-model-10` | `security_red_blue_council` | 10 | C-D32 deep-security-threat-model-10 |
| — | `g-up01-stakeholder-user-panel` | `stakeholder_user_panel` | 6 | none (spec-required gap fill) |

`preset` is an archetype LABEL drawn from the schema's 24-value `preset_name` enum
plus `custom`; `council_id` is the identity. Two files may legitimately share a
label at different tiers (17 and 32 are both `security_red_blue_council`: the
45-minute form and the 3-hour STRIDE form).

## Per-file headline dials

| file | the dials you will actually turn |
|---|---|
| 17 | `budgets.experiments` / `protocol.experiments.max_experiments` (attack budget) · `stopping.expression.experiments_passed` (reproduction quota) · `protocol.experiments.runner` |
| 18 | `objective.statement` (the motion) · `protocol.rounds` + `stopping.hard_caps.max_rounds` · `protocol.turn.max_tokens` + `budgets.speaking_quota_per_participant` (token parity) |
| 19 | `protocol.rounds.max` (depth cap) · `stopping.expression.evidence_items` · `voting.method` (`synthesis_only` by design — changing it changes the council's kind) |
| 20 | `protocol.rounds.min` (cycles) · `targets.diversity_index` + the matching stop leaf (distance floor) · `targets.dedup.max_similarity` |
| 21 | `protocol.sequence` order (hat order) · `protocol.turn.max_words` · `targets.unique_ideas` |
| 22 | `targets.unique_ideas` **and** the `unique_ideas` stop leaf — move together or SEM-007 fails · `protocol.sequence[0].quotas.ideas_per_participant` · `participants.anonymity.reveal_after_round` |
| 23 | `protocol.rounds` (rounds) · `participants.anonymity.mode` · `voting.belief_aggregation.method` · `voting.score_scale` (the estimate unit) |
| 24 | `stopping.expression.independent_positions` (hypothesis floor) · `targets.coverage_score` (diagnosticity threshold) · `protocol.speaking_order` |
| 25 | `participants.roster[0]` (the commander) · `protocol.turn.time_limit_seconds` (heartbeat) · `stopping.expression` (detector-green vs stand-down) |
| 26 | `protocol.sequence[1]` (why depth) · `protocol.sequence[2]` + `targets.coverage_score` (blast-radius scope) · `stopping.expression.evidence_items` |
| 27 | `stopping.expression.counterexamples_found` (attack floor) · the `custom:attacks_mapped_to_real_incident` leaf · `protocol.sequence[0].quotas` |
| 28 | the four stakeholder seats · `protocol.sequence[0]` (BATNA gate) · `voting.method` · `consensus.dissent_policy.min_dissenters_to_block` |
| 29 | `participants.roster` (who holds the two keys — keep the vendors distinct) · `participants.information_partition.partitions` (the no-shared-brief rule) · **do not** change `voting.tie_break` from `no_decision`: a tie-break IS the single-key bypass |
| 30 | `budgets.time_minutes` + `stopping.hard_caps.max_minutes` (the window) · reviewer seats (comment sources) · `stopping.minimum_deliberation.min_minutes` |
| 31 | `topology.subcouncils` (each entry is a COMPLETE CouncilSpec, validated recursively) · `topology.fan_in.reducer` · `stopping.expression.subcouncils_complete` must equal the subcouncil count · `budgets.tokens` |
| 32 | `protocol.sequence[1]` + `targets.categories` (attack-surface taxonomy) · `stopping.expression.experiments_passed` (reproduction quota) · `voting.veto.holders` |
| user panel | the four usage positions (daily / new / power / recovering) · `participants.anonymity.reveal_after_round` · `voting.method` (score + median: it rates, it does not elect) · `protocol.critique_intensity` (`gentle` on purpose) |

## Editing rules that the validator will enforce on you

These are the coupling constraints that catch real edits. All seven were measured
firing on a known-broken mutation (`_lane2_probe_controls.py`).

1. **Seat count and roster move together.** `participants.selection.mode == "exact"`
   requires `len(roster) == count.exact_n` (SEM-004). Raising the count alone is
   rejected — the editability probe relies on exactly this.
2. **`source_expression` must parse to the identical tree** as
   `stopping.expression` (SEM-001). It is present on 16 of 17 files as a
   machine-checked human-readable form. Change one, change both.
3. **Every id you reference must be in the roster** — chair, veto holders,
   committee/caucus members, stage participants (SEM-006).
4. **An idea-count stop leaf needs an idea-generating stage AND a matching
   `targets.unique_ideas`** (SEM-007). Only file 22 gates on one.
5. **`consensus.minority_report: "required"` needs `minority_report` in
   `outcomes.allowed`** (SEM-009).
6. **`stopping.hard_caps.max_rounds` must not fall below `protocol.rounds.min`**
   (SEM-011).
7. **The schema is closed.** An unknown key anywhere is a hard failure, so there
   is no place to stash an ad-hoc field: extend the schema or use
   `metadata.notes`.

## Known substrate limits hit while authoring these

* **A `custom:` metric that declares a `producer` cannot coexist with
  `source_expression`.** `councilspec.expression.parse()` never emits `producer`,
  so SEM-001's tree comparison always fails. File 27 is the only file affected;
  it omits `source_expression` and carries the human form in `metadata.notes`.
  Measured in both directions (finding F-P2-01).
* **`fishbowl` is a protocol STAGE kind but not a topology kind.** The user panel
  expresses its fishbowl as a stage under a `chair_led` topology.
* **There is no unbounded council.** C-S25's card says `wall<=unbounded`;
  `stopping.hard_caps` must name an `on_cap` behaviour, so the war room uses 48
  heartbeat rounds with `on_cap: escalate_to_owner` — a cap the owner sees, not a
  decision the council makes. Disclosed in that file's notes.
* **Four design cards' seat counts disagree with their own roles lines** (17, 22,
  23, 31). Each instance seats the enumerated roles and records the discrepancy.

## Regenerating / re-checking

```
cd platform/council/presets
python _lane2_emit.py             # writes the 17 files, then validates them off disk
python _lane2_probe_controls.py   # detector control + F-P2-01 + cross-lane coverage
python _lane2_probe_editable.py   # documented / dial-moves / guard-fires / pure-JSON
```

The JSON files are the source of truth. `_lane2_*.py` are authoring conveniences:
hand-edit the JSON freely and it will keep validating — re-running the emitter
would overwrite hand edits, so edit the builder too if a change should be durable.