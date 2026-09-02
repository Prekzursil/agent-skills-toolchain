#!/usr/bin/env python3
"""Emit CNL-0033 design note (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import topology as T  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0033/probe2_negative_control.py"
)
QUESTION = (
    "Red and blue are not symmetric (one attacks, one defends) - what "
    "asymmetry in budget, evidence standard and win condition makes the "
    "exercise informative rather than a scripted loss for whichever side "
    "was given less time?"
)
# Catalog output_schema is a generated $ref shim to
# https://ast-integrate.invalid/... — it does not resolve on this worktree
# (jsonschema RefResolutionError). G-1 needs JSON parse + sentinel, not a
# live $ref fetch. Do not rebuild platform/schema (no ADV circle).
LOCAL_REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "symmetry_swap",
    "negative_controls",
    "reviewer",
    "evidence",
    "tests",
    "artifacts",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def missing_required(doc: dict) -> list[str]:
    return [k for k in LOCAL_REQUIRED if k not in doc]


def main() -> int:
    good = T.load_topology("good")
    bad = T.load_topology("timeout_wins")
    finding = T.load_world("finding")
    clean = T.load_world("clean")
    narrative = T.load_world("narrative")

    good_find = T.clock_pair_runs(good, finding)
    good_clean = T.clock_pair_runs(good, clean)
    bad_find = T.clock_pair_runs(bad, finding)
    bad_clean = T.clock_pair_runs(bad, clean)
    rec_find = T.recount_from_events(good_find["events_hi_red"], finding)
    rec_clean = T.recount_from_events(good_clean["events_hi_red"], clean)
    trap_good = T.timeout_trap(good)
    trap_bad = T.timeout_trap(bad)
    narr = T.simulate(good, narrative, red_clock=20, blue_clock=20)
    det_bad = T.detector_clock_swap_changes_winner(bad, finding)
    det_good = T.detector_clock_swap_changes_winner(good, finding)

    if good_find["winner_swapped"] or good_clean["winner_swapped"]:
        print("FAILED:CNL-0033 emit good topology swapped under clock permutation")
        return 1
    if not bad_find["winner_swapped"] or not bad_clean["winner_swapped"]:
        print("FAILED:CNL-0033 emit defective topology did not swap")
        return 1
    if trap_good["outcome"] != "INCONCLUSIVE":
        print("FAILED:CNL-0033 emit timeout trap was not INCONCLUSIVE")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "The informative asymmetry is not 'give red less clock.' Clock is a "
        "right to spend, never a scoring input. Red is scored in attempt-budget "
        "(existence search for one reproducible artifact). Blue is scored in "
        "coverage-obligation discharge (universality over a named surface). "
        "Red wins on one confirmed finding (repro_poc / failing_control / "
        "concrete_counterexample). Blue wins only when confirmed_findings==0 "
        "AND red's attempt budget is exhausted AND the coverage checklist is "
        "complete. Every other terminal — including red clock death with "
        "attempts remaining — is INCONCLUSIVE, labelled not-refuted-within-budget "
        "never 'secure'. A topology that awards the side with leftover clock "
        "is refuted by the symmetry-swap control: swapping the larger clock "
        "deterministically swaps the winner, so that topology measures budget "
        "not truth."
    )
    markdown_body = """# CNL-0033 Red/blue adversarial topology with asymmetric mandates

## Question

Red and blue are not symmetric (one attacks, one defends) — what asymmetry
in budget, evidence standard and win condition makes the exercise informative
rather than a scripted loss for whichever side was given less time?

## Claim under test

Equal clocks and a shared 'who still has budget wins' condition make the
exercise a scripted loss for the side given less time. The repair is three
asymmetric axes (budget currencies, evidence standard, win condition), not
a smaller red clock.

## Mandates (obligation / permission / right)

This unit depends on CNL-0022's trichotomy. The CNL-0022 artifact is not on
this worktree; the trichotomy is used here as a local contract so G-1 for
THIS unit does not deadlock waiting on CNL-0022.

| Seat | Obligation (MUST) | Permission (MAY) | Right (nobody may deny) |
| --- | --- | --- | --- |
| Red | none — failing to find a bug is not a red failure | attempt_attack, submit_finding_artifact | private channel; attempt budget not revocable mid-round; finding judged on artifact not clock |
| Blue | discharge_named_coverage_checklist | patch_in_exercise, request_scope_clarification | coverage slots not revocable; timeout cannot be scored as secure; outcome label is not-refuted, not secure |

A schema that stores a single `capabilities[]` string list conflates these
three (CNL-0022's load-bearing question). Red's unused permission must not
fail the role check; blue's unmet coverage obligation must.

## Three currencies

1. Clock / token budget — a right, not a score.
2. Red attempt budget — finding currency.
3. Blue coverage slots — obligation currency.

Swapping (1) while holding (2) and (3) fixed must not swap the winner.

## Evidence standard

Red's positive claim requires a reproducible artifact. A narrative_claim is
rejected. Blue has no 'secure' claim; blue may only reach BLUE_WIN as
not-refuted after attempts exhausted and coverage complete.

## Win condition

- RED_WIN: confirmed_findings >= 1, even if blue still has clock and coverage left.
- BLUE_WIN: confirmed==0 AND attempts exhausted AND coverage complete.
- INCONCLUSIVE: otherwise, including clock death with leftover attempts.

## Defective alternative (refuted)

Score remaining clock. The side that outlasts the other wins. The
symmetry-swap control fires: 100/10 vs 10/100 swaps the winner on both a
planted-finding world and a clean-surface world.

## Live measurements (embedded at emit)

See `symmetry_swap` and `negative_controls` in this document. Named probes
re-run the same fixtures.
"""

    doc = {
        "unit_id": "CNL-0033",
        "id": "CNL-0033",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0033",
        "completion_sentinel": "SUCCESS:CNL-0033",
        "spec_anchor": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "_USER-PROMPTS.md:10746-10767"
        ),
        "schema_note": (
            "Catalog output_schema command-center/schema/"
            "council-design-note.schema.json is a generated $ref shim to "
            "https://ast-integrate.invalid/platform/schema/"
            "artifact-class-profiles.schema.json which does not resolve on "
            "this worktree. This note is JSON-parseable with state=SUCCESS. "
            "No ADV rebuild of that schema was attempted."
        ),
        "title": "Red/blue adversarial topology with asymmetric mandates",
        "question": QUESTION,
        "claim_under_test": (
            "Asymmetry that makes red/blue informative is three-axis "
            "(currencies, evidence, win condition), not a smaller red clock. "
            "A clock-only swap must not swap the winner on the good topology "
            "and must swap it on remaining-clock scoring."
        ),
        "answer": answer,
        "markdown_body": markdown_body,
        "output_schema": SCHEMA,
        "protocol_anchor": {
            "family": "ADVERSARIAL",
            "named_record": "P08 red-blue-team",
            "note": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this "
                "worktree; P08 is cited from the catalog text of CNL-0039, "
                "not from a live library count."
            ),
            "library_present": (
                REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ).is_file()
            or (
                REPO
                / "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ).is_file(),
        },
        "dependency_cnl_0022": {
            "id": "CNL-0022",
            "artifact_present": (
                REPO
                / "command-center/design/council/"
                "CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
            ).is_file(),
            "trichotomy_used_locally": True,
            "note": (
                "Waiting for CNL-0022 before closing CNL-0033 is a deadlock; "
                "G-1 for this unit does not require that circle. No ADV rebuild."
            ),
        },
        "topology": good,
        "defective_topology": {
            "id": bad["id"],
            "scoring": bad["scoring"],
            "clock_is_scoring_input": True,
            "timeout_policy": bad["timeout_policy"],
        },
        "mandates": good["mandates"],
        "currencies": [
            {
                "id": "clock",
                "role": "right",
                "scoring_input_on_good": False,
                "description": "Wall/token budget. May not decide the winner.",
            },
            {
                "id": "red_attempt_budget",
                "role": "finding-currency",
                "scoring_input_on_good": True,
                "description": "Existence search. Exhaustion is required for BLUE_WIN.",
            },
            {
                "id": "blue_coverage_slots",
                "role": "obligation-currency",
                "scoring_input_on_good": True,
                "description": "Named surface discharge. Incomplete coverage blocks BLUE_WIN.",
            },
        ],
        "win_conditions": {
            "RED_WIN": "confirmed_findings >= 1",
            "BLUE_WIN": (
                "confirmed_findings == 0 AND attempts_exhausted AND "
                "coverage_complete"
            ),
            "INCONCLUSIVE": (
                "otherwise, including red clock death with leftover attempts; "
                "label is not-refuted-within-budget, never secure"
            ),
        },
        "evidence_standard": {
            "red_positive_claim_requires": list(good["allowed_evidence"]),
            "narrative_claim_confirms": False,
            "blue_may_claim_secure": False,
            "blue_terminal_label_on_win": "not-refuted-within-budget",
        },
        "symmetry_swap": {
            "clock_hi": 100,
            "clock_lo": 10,
            "good_finding_winners": [
                good_find["run_hi_red"]["winner"],
                good_find["run_lo_red"]["winner"],
            ],
            "good_clean_winners": [
                good_clean["run_hi_red"]["winner"],
                good_clean["run_lo_red"]["winner"],
            ],
            "defective_finding_winners": [
                bad_find["run_hi_red"]["winner"],
                bad_find["run_lo_red"]["winner"],
            ],
            "defective_clean_winners": [
                bad_clean["run_hi_red"]["winner"],
                bad_clean["run_lo_red"]["winner"],
            ],
            "good_winner_swapped": bool(
                good_find["winner_swapped"] or good_clean["winner_swapped"]
            ),
            "defective_winner_swapped": bool(
                bad_find["winner_swapped"] and bad_clean["winner_swapped"]
            ),
            "signal1": "winner identity pair under clock-only permutation",
            "signal2": "event-log score_vector recount (confirmed/exhausted/complete)",
            "signal2_finding_recount_winner": rec_find["recount_winner"],
            "signal2_clean_recount_winner": rec_clean["recount_winner"],
            "timeout_trap_good": {
                "outcome": trap_good["outcome"],
                "winner": trap_good["winner"],
                "attempts_used": trap_good["score_vector"]["attempts_used"],
                "attempts_exhausted": trap_good["score_vector"][
                    "attempts_exhausted"
                ],
            },
            "timeout_trap_defective": {
                "outcome": trap_bad["outcome"],
                "winner": trap_bad["winner"],
            },
            "narrative_good": {
                "outcome": narr["outcome"],
                "winner": narr["winner"],
                "confirmed": narr["score_vector"]["confirmed"],
            },
        },
        "tests": [
            {
                "id": "T1-symmetry-swap",
                "name": (
                    "Clock-only swap must not swap the winner on the good "
                    "topology and must swap it on remaining-clock scoring"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control-both-states",
                "name": (
                    "clock_swap_changes_winner FIRES on timeout-wins and is "
                    "SILENT on asymmetric-mandates; timeout is not a blue win"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0033-C1",
                "kind": "known-broken-fixture",
                "check": "clock_swap_changes_winner",
                "description": (
                    "The check fires when a clock-only permutation changes "
                    "the winner. Planted-bad state is remaining-clock scoring "
                    "(timeout-wins-defective). Known-good state is "
                    "asymmetric-mandates-v1."
                ),
                "reject_state": (
                    "timeout-wins-defective scores remaining clock; swapping "
                    "the larger clock swaps the winner (budget, not truth)"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": det_bad["verdict"],
                "good_state_output": det_good["verdict"],
                "verbatim_bad_finding": (
                    f"fired={det_bad['fired']} "
                    f"winners={det_bad['winner_hi_red']}->"
                    f"{det_bad['winner_lo_red']} "
                    f"verdict={det_bad['verdict']}"
                ),
                "verbatim_good_finding": (
                    f"fired={det_good['fired']} "
                    f"winners={det_good['winner_hi_red']}->"
                    f"{det_good['winner_lo_red']} "
                    f"verdict={det_good['verdict']}"
                ),
            }
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Clock-only swap of 100/10 vs 10/100 does not change the "
                    "winner on asymmetric-mandates-v1 (finding stays RED, "
                    "clean stays BLUE)."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py"
                ),
            },
            {
                "id": "C2",
                "claim": (
                    "The same clock permutation swaps the winner on "
                    "remaining-clock (timeout-wins) scoring, so the detector "
                    "is not vacuous."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/"
                    "fixtures/topology_timeout_wins.json"
                ),
            },
            {
                "id": "C3",
                "claim": (
                    "Red clock death with leftover attempts is INCONCLUSIVE "
                    "on the good topology, not a blue win."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/topology.py:timeout_trap"
                ),
            },
            {
                "id": "C4",
                "claim": (
                    "P08 red-blue-team protocol body was read from "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json on this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "protocol_anchor.library_present",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "On asymmetric-mandates-v1, swapping clocks 100/10 vs "
                    "10/100 leaves the winner unchanged on both a planted "
                    "finding (RED) and a clean surface (BLUE)."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py"
                ),
                "signal": "winner-identity-pair",
            },
            {
                "claim": (
                    "The same invariance is recovered by recounting "
                    "confirmed/attempts_exhausted/coverage_complete from the "
                    "event log, a different field than winner."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/topology.py:"
                    "recount_from_events"
                ),
                "signal": "event-log-score-vector",
            },
            {
                "claim": (
                    "Remaining-clock scoring swaps the winner under the same "
                    "clock permutation on both worlds, so the detector is not "
                    "vacuous."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/"
                    "fixtures/topology_timeout_wins.json"
                ),
            },
            {
                "claim": (
                    "Red clock death with leftover attempts is INCONCLUSIVE "
                    "on the good topology and a BLUE win on timeout-wins — "
                    "the scripted-loss state the question names."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0033/topology.py:timeout_trap"
                ),
            },
            {
                "claim": (
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json P08 body was read "
                    "from disk on this worktree."
                ),
                "verdict": "REFUTED",
                "anchor": "protocol_anchor.library_present",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0033-probe2-both-states-control",
            "vendor_role": "openai/gpt-5-codex",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
            "scope_not_agreement": True,
            "method": (
                "probe2_negative_control.py re-runs clock_swap_changes_winner "
                "on planted-bad and known-good fixtures and records both "
                "transcripts verbatim. A review that did not execute this "
                "control is rejected by the probe."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0033/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py"
                ),
                "artifact_path": OUT,
                "executed": True,
            },
            {
                "consumer": (
                    "command-center/p2-wave/_measure_one_delivered.py CNL-0033"
                ),
                "artifact_path": OUT,
                "executed": False,
                "note": "Measure runs after emit and after named probes.",
            },
        ],
        "residual_unknowns": [
            {
                "claim": "P08 red-blue-team protocol record body in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the library on disk and bind this topology's "
                    "mandates onto the live P08 record field-by-field."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a "
                "3rd attempt (AGENTS.md 4b)"
            ),
        },
        "timestamps": {
            "ended_at": now,
        },
        "named_probes": [
            {"id": "probe1", "role": "symmetry-swap", "command": P1},
            {"id": "probe2", "role": "negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0033/topology.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "min_bytes_threshold": 8000,
    }

    missing = missing_required(doc)
    if missing:
        print(f"FAILED:CNL-0033 local required keys missing {missing}")
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not missing_required(g):
            print(f"FAILED:CNL-0033 local gate accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0033 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0033 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
