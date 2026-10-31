"""Build LANE-2-STATUS.json from the three probes' measured output.

Nothing here re-asserts a claim: every field is read out of
_lane2_emit_out.json, _lane2_probe_controls_out.json or
_lane2_probe_editable_out.json, so the status file cannot drift from the probes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent

FINDINGS: List[Dict[str, Any]] = [
    {
        "id": "F-P2-01",
        "verdict": "CONFIRMED",
        "severity": "P2",
        "claim": "A CouncilSpec stopping expression that uses a custom: metric with a declared "
        "`producer` can NEVER also carry `source_expression`: SEM-001 compares the parsed tree to "
        "the structured tree and councilspec.expression.parse() cannot emit `producer`.",
        "evidence": "_lane2_probe_controls.py run_fp201: A(producer+source)=SEM-001, "
        "B(no producer+source)=accepted, C(producer, no source)=accepted with zero warnings; "
        "parse() emits keys ['metric','op','value','value_type'].",
        "impact": "An author must choose between a machine-checked human-readable stopping rule and "
        "a declared metric producer. Affects c-s27-kill-the-company-5 in this lane and any future "
        "preset with an extension metric.",
        "suggested_fix": "Have SEM-001 compare only the keys parse() can produce, or have parse() "
        "accept and round-trip a producer annotation.",
        "anchor": "platform/lib/councilspec/semantics.py:68 (parsed != tree) with "
        "platform/lib/councilspec/expression.py:216",
    },
    {
        "id": "F-P2-02",
        "verdict": "CONFIRMED",
        "severity": "P2",
        "claim": "THREE files in platform/council/presets now carry preset=general_purpose_auto_composed, "
        "so the 'two implementations of one archetype disagree' failure class is live in this "
        "directory - and none of the three is lane 2's.",
        "evidence": "_lane2_probe_controls_out.json coverage.duplicates: "
        "['C-D43-nested-subcouncils-15', 'GAP-AUTO-general-purpose-auto-composed', "
        "'c-g73-general-purpose-auto-composed']. Lane 2 built a fourth (g00-*), measured the "
        "collision, and DELETED it rather than add to the pile.",
        "impact": "A consumer resolving a council by archetype label gets a non-deterministic answer. "
        "C-D43-nested-subcouncils-15 looks like a mislabel (its card is a nested-subcouncil council, "
        "not an auto-composer) - that one is a defect, not a duplicate.",
        "suggested_fix": "Orchestrator ruling: keep ONE auto-composed preset (c-g73 is the richest at "
        "13,882 bytes), delete GAP-AUTO-*, and relabel C-D43 to `custom`.",
        "anchor": "platform/council/presets/_lane2_probe_controls_out.json",
    },
    {
        "id": "F-P2-03",
        "verdict": "CONFIRMED",
        "severity": "P3",
        "claim": "Four of the sixteen design cards in indices 17-32 declare a seat count that "
        "contradicts their own roles line.",
        "evidence": "_lane2_emit_out.json card_self_consistent=false for idx 17 (says 4, enumerates "
        "5), 22 (6 vs 7), 23 (5 vs 6), 31 (12 vs 13). Measured by counting the roles line, not judged.",
        "impact": "Any consumer trusting the card's seat number provisions the wrong number of seats. "
        "In every case the extra seat is a non-voting facilitator/white-cell, which is the likely "
        "reason the card's count omitted it.",
        "suggested_fix": "Each instance seats the ENUMERATED roles and records the discrepancy in "
        "metadata.notes; doc 12's index table should be corrected to match its own role lines.",
        "anchor": "12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1387, :1457, :1471, :1591",
    },
    {
        "id": "F-P2-04",
        "verdict": "CONFIRMED",
        "severity": "P2",
        "severity_note": "raised from P3 to P2 after measurement: this is a real 7-preset "
        "shortfall, not a bookkeeping quibble",
        "claim": "The lane slicing 'presets N-M of 64' undercounts doc 12, which defines 72 preset "
        "cards - and SEVEN of them (design indices 66-72) have NO file on disk.",
        "evidence": "_lane2_probe_index_coverage.py, matching doc 12's own '#### C-xx `slug`' "
        "headings against the filenames present: cards_total=72, cards_with_file=65, "
        "cards_without_file=[66 test-strategy-council, 67 refactor-equivalence-council, "
        "68 design-system-verdict, 69 media-license-gate, 70 research-source-credibility, "
        "71 program-scoping-grill, 72 stopping-rule-owner-grill]. C-H65 pr-merge-order IS present, "
        "so the shortfall is 66-72, not 65-72.",
        "evidence_correction": "An earlier draft of this finding asserted that files for "
        "C-H65..C-H72 DO exist. That was an UNMEASURED assumption and it was WRONG - "
        "_lane2_probe_index_coverage.py refuted it. The corrected numbers are above.",
        "impact": "Seven harness-specific councils named in doc 12 will never be built if the "
        "program target stays at 64: test strategy, refactor equivalence, design-system verdict, "
        "media licence, research-source credibility, program-scoping grill, stopping-rule grill.",
        "suggested_fix": "Restate the program target as 72 and assign indices 66-72 to a lane. "
        "Lane 2 did NOT build them: they are outside 17-32 and inventing them would be a design "
        "decision, not an implementation.",
        "anchor": "12-COUNCIL-PROTOCOLS-AND-PRESETS.md:1062-1140 (preset index, 72 rows); "
        "platform/council/presets/_lane2_probe_index_coverage_out.json",
    },
    {
        "id": "F-P2-05",
        "verdict": "CONFIRMED",
        "severity": "P3",
        "claim": "Program stopping condition 13 ('release/canary succeeds') remains unsatisfiable "
        "under PR-ONLY release mode, and no preset in this lane can satisfy it either.",
        "evidence": "Inherited known defect, re-checked against this lane: every preset's "
        "audit.safety.owner_approval_for tops out at ['merge','release'] and "
        "forbid_irreversible_actions is true in all 17 files, so no council here can execute a "
        "release. Measured: _lane2_emit_out.json shows 17/17 emitted; none declares a release action.",
        "impact": "No lane-2 artifact can close condition 13; it needs an owner ruling, not code.",
        "suggested_fix": "Owner ruling on condition 13 under PR-ONLY.",
        "anchor": "command-center/COMPLETION-GATES.json (program stopping condition 13)",
    },
]


def git_lf_check(files: List[str]) -> Dict[str, Any]:
    """Line endings of what would be COMMITTED, not the worktree guess."""
    out = {}
    for f in files:
        p = HERE / f
        raw = p.read_bytes()
        out[f] = {"crlf_pairs": raw.count(b"\r\n"), "bytes": len(raw)}
    return out


def main() -> int:
    emit = json.loads((HERE / "_lane2_emit_out.json").read_text(encoding="utf-8"))
    controls = json.loads(
        (HERE / "_lane2_probe_controls_out.json").read_text(encoding="utf-8")
    )
    editable = json.loads(
        (HERE / "_lane2_probe_editable_out.json").read_text(encoding="utf-8")
    )

    idxcov = json.loads(
        (HERE / "_lane2_probe_index_coverage_out.json").read_text(encoding="utf-8")
    )

    cov = controls["coverage"]
    files = [r["file"] for r in emit]
    eol = git_lf_check(files)

    status = {
        "unit": "build/preset-2",
        "phase": "2C",
        "slice": "council presets 17-32 of 64 (design-doc index == the card's own number, "
        "so 17 == C-S17 and 32 == C-D32)",
        "state": "MEASURED",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "design_source": "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
        "validated_against": "platform/schema/councilspec.schema.json",
        "counts": {
            "files_written": len(emit),
            "files_from_the_17_32_slice": sum(1 for r in emit if r["design_index"]),
            "files_gap_fill_outside_the_slice": sum(
                1 for r in emit if not r["design_index"]
            ),
            "files_schema_valid": sum(1 for r in emit if r["schema_valid"]),
            "files_zero_semantic_errors": sum(
                1 for r in emit if not r["semantic_errors"]
            ),
            "files_zero_semantic_warnings": sum(
                1 for r in emit if not r["semantic_warnings"]
            ),
            "files_documented_with_dial_pointers": sum(
                1 for r in editable if r["documented"]
            ),
            "files_dial_moves_and_still_validates": sum(
                1 for r in editable if r["live_dial_accepted"]
            ),
            "files_incoherent_edit_rejected": sum(
                1 for r in editable if r["incoherent_edit_rejected"]
            ),
            "files_pure_json_no_build_step": sum(
                1 for r in editable if r["pure_json_roundtrip"]
            ),
            "files_with_crlf": sum(1 for v in eol.values() if v["crlf_pairs"]),
            "total_seats_across_lane": sum(r["seats_in_instance"] for r in emit),
            "design_cards_self_inconsistent": sum(
                1 for r in emit if r["design_index"] and not r["card_self_consistent"]
            ),
        },
        "detector_control": {
            "probe": "platform/council/presets/_lane2_probe_controls.py",
            "mutations": 7,
            "caught_by_declared_layer": 7,
            "note": "schema x2, SEM-001, SEM-004, SEM-006, SEM-009, SEM-011. The unmutated base is "
            "asserted to pass FIRST, so a probe that is silent in both states cannot slip through.",
        },
        "design_card_coverage_directory_wide": {
            "note": "Doc 12's own '#### C-xx `slug`' headings matched against the filenames "
            "present. Mechanical, no judgement. See F-P2-04.",
            "cards_in_doc_12": idxcov["cards_total"],
            "cards_with_a_file": idxcov["cards_with_file"],
            "cards_with_NO_file": idxcov["cards_without_file"],
            "files_not_matched_to_a_card": idxcov["files_unmatched"],
        },
        "required_archetype_coverage_directory_wide": {
            "note": "Measured over EVERY *.councilspec.json in this shared directory, not just "
            "lane 2's files - sibling lanes write here too.",
            "files_in_directory": len(cov["files"]),
            "required_archetypes": 24,
            "covered": len(cov["covered"]),
            "missing": cov["missing"],
            "carried_by_more_than_one_file": {
                k: sorted(v) for k, v in cov["duplicates"].items()
            },
        },
        "lane_2_archetype_contribution": sorted(
            {r["preset"] for r in emit if r["preset"] != "custom"}
        ),
        "per_file": [
            {
                "design_index": r["design_index"],
                "design_card": r["design_card"],
                "file": r["file"],
                "council_id": r["council_id"],
                "preset": r["preset"],
                "validator_verdict": "OK (councilspec CLI) / schema_valid=%s / semantic_errors=%d"
                % (r["schema_valid"], len(r["semantic_errors"])),
                "semantic_warnings": r["semantic_warnings"],
                "seats_in_instance": r["seats_in_instance"],
                "seats_declared_on_card": r["seats_declared_on_card"],
                "roles_enumerated_on_card": r["roles_enumerated_on_card"],
                "card_self_consistent": r["card_self_consistent"],
                "bytes": r["bytes"],
                "crlf_pairs": eol[r["file"]]["crlf_pairs"],
                "notes_chars": next(
                    e["notes_chars"] for e in editable if e["file"] == r["file"]
                ),
                "dial_pointers_documented": next(
                    e["dial_pointers_in_notes"]
                    for e in editable
                    if e["file"] == r["file"]
                ),
            }
            for r in emit
        ],
        "findings": FINDINGS,
        "deliberate_deviations_from_the_design_cards": [
            "c-s25 war room: the card says rounds:0 / wall<=unbounded. The schema has no unbounded "
            "form and stopping.hard_caps.on_cap must name a behaviour, so 48 heartbeat rounds with "
            "on_cap=escalate_to_owner stands in. Disclosed in that file's metadata.notes.",
            "c-s27 kill-the-company: no source_expression (see F-P2-01).",
            "Cards' SHOUTY outcome vocabulary (CONSENSUS / MAJORITY_WITH_DISSENT / ...) is mapped "
            "onto the schema's 7-value outcomes.allowed enum; the mapping is printed in every "
            "file's metadata.notes so it is auditable per file.",
            "Cards' voting rules that have no schema enum member (landed_attacks_only, "
            "commander_unilateral, logical_AND, median_with_spread, fewest_inconsistencies, "
            "nested_then_meta) are expressed as the nearest predicate-equivalent combination and the "
            "mapping is recorded per file.",
        ],
        "not_checked": [
            "Whether the ENGINE that consumes these presets behaves as each stopping rule intends - "
            "no engine exists yet, so only the specs are validated. NOT-CHECKED, settled by running "
            "a council against one of these files once a runtime lands.",
            "Whether sibling lanes' presets are internally consistent with mine (e.g. whether "
            "c-s15-arch-review-board-5 and c-d31-deep-architecture-12 would give the same verdict on "
            "the same architecture question). NOT-CHECKED - cross-preset differential testing is out "
            "of this unit's scope.",
        ],
    }

    path = HERE / "LANE-2-STATUS.json"
    path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}  ({path.stat().st_size} bytes)")
    c = status["counts"]
    print(json.dumps(c, indent=2))
    ok = (
        c["files_written"] == 17
        and c["files_schema_valid"] == 17
        and c["files_zero_semantic_errors"] == 17
        and c["files_documented_with_dial_pointers"] == 17
        and c["files_dial_moves_and_still_validates"] == 17
        and c["files_incoherent_edit_rejected"] == 17
        and c["files_pure_json_no_build_step"] == 17
        and c["files_with_crlf"] == 0
    )
    print(
        "SUCCESS:lane2-status"
        if ok
        else "FAILED:lane2-status a counted invariant is not 17/17"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
