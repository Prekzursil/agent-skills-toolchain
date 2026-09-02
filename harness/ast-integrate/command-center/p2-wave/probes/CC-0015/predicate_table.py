"""Twenty-one encoded stopping-condition predicates for CC-0015.

This module is data: predicate specs the generic evaluator walks.
Condition 13 is not a special case in the evaluator. It is an ordinary
encoding that carries an optional amendment slot any condition may use.
"""
from __future__ import annotations

COST_SPEC = {
    "class": "place-verbatim-spec",
    "approx_seconds": 60,
    "approx_usd": 0,
}
COST_OPTIONS = {
    "class": "option-disposition-join",
    "approx_seconds": 180,
    "approx_usd": 0,
}
COST_LOCAL = {
    "class": "local-file-read",
    "approx_seconds": 10,
    "approx_usd": 0,
}
COST_SUITES = {
    "class": "negative-control-census",
    "approx_seconds": 240,
    "approx_usd": 0,
}
COST_MATRIX = {
    "class": "compatibility-matrix-cells",
    "approx_seconds": 120,
    "approx_usd": 0,
}
COST_BENCH = {
    "class": "benchmark-ledger",
    "approx_seconds": 300,
    "approx_usd": 0,
}
COST_SCAN = {
    "class": "release-time-scanner",
    "approx_seconds": 600,
    "approx_usd": 0,
}
COST_EXTRACT = {
    "class": "independent-floor-extractor",
    "approx_seconds": 120,
    "approx_usd": 0,
}
COST_UNK = {
    "class": "unknowns-register-two-part",
    "approx_seconds": 180,
    "approx_usd": 0,
}

ALLOWED_DISPOSITIONS = (
    "IMPLEMENTED",
    "SUPERSEDED",
    "REJECTED-WITH-OWNER-REASONING",
)

SC13_AS_WRITTEN = "Release/canary succeeds."
SC13_AMENDED = (
    "Merged PR plus green REL-0004 (install), REL-0005 (upgrade) and "
    "REL-0006 (rollback) rehearsal receipts."
)

SC13_AS_WRITTEN_SPEC = {
    "kind": "any_of",
    "parts": [
        {"kind": "bool", "key": "canary_succeeded"},
        {"kind": "bool", "key": "marketplace_release_succeeded"},
    ],
}

SC13_AMENDED_SPEC = {
    "kind": "all_of",
    "parts": [
        {"kind": "bool", "key": "merged_pr"},
        {
            "kind": "receipts_green",
            "ids": ["REL-0004", "REL-0005", "REL-0006"],
        },
    ],
}


def _p(
    *,
    id: int,
    spec_line: int,
    text: str,
    text_confidence: str,
    catalog_anchor: str,
    spec: dict,
    settling_probe: str,
    probe_cost: dict,
    **extra,
) -> dict:
    row = {
        "id": id,
        "spec_line": spec_line,
        "text": text,
        "text_confidence": text_confidence,
        "catalog_anchor": catalog_anchor,
        "as_written": spec,
        "settling_probe": settling_probe,
        "probe_cost": dict(probe_cost),
    }
    row.update(extra)
    return row


def _absent(id: int, spec_line: int) -> dict:
    return _p(
        id=id,
        spec_line=spec_line,
        text=(
            f"Verbatim stopping-condition text for spec line {spec_line} "
            "is not on this worktree (_USER-PROMPTS.md absent)."
        ),
        text_confidence="ABSENT-VERBATIM",
        catalog_anchor="line number only; no catalog quotation of this stopping-condition line",
        spec={"kind": "absent_verbatim", "spec_line": spec_line},
        settling_probe=(
            f"Place _USER-PROMPTS.md and encode the predicate at line {spec_line} "
            "from the verbatim sentence, then re-run the same evaluator."
        ),
        probe_cost=COST_SPEC,
    )


ENCODINGS: list[dict] = [
    _p(
        id=1,
        spec_line=11378,
        text=(
            "Every selected option id is IMPLEMENTED, SUPERSEDED, or "
            "REJECTED-WITH-OWNER-REASONING."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 extract CANONICAL_LINES[11378]; SYN-0028 / catalog "
            "stopping condition 1, _USER-PROMPTS.md:11378"
        ),
        spec={
            "kind": "closed_set",
            "ids_key": "selected_option_ids",
            "map_key": "dispositions",
            "allowed": list(ALLOWED_DISPOSITIONS),
            "required_nonempty": True,
        },
        settling_probe=(
            "Join every selected option id through the namespace registry to a "
            "terminal disposition; a missing join is NOT-CHECKED, a non-terminal "
            "disposition is FALSE."
        ),
        probe_cost=COST_OPTIONS,
    ),
    _absent(2, 11379),
    _absent(3, 11380),
    _p(
        id=4,
        spec_line=11381,
        text="No required test is red.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "WORK-UNIT-CATALOG.json SYN-0043 tests_required: "
            "'condition 4 (no required test is red)'"
        ),
        spec={
            "kind": "none_red",
            "key": "required_tests",
            "required_nonempty": True,
        },
        settling_probe=(
            "Read the required-test ledger; any status=red or red=true is FALSE. "
            "A missing ledger is NOT-CHECKED."
        ),
        probe_cost=COST_LOCAL,
    ),
    _p(
        id=5,
        spec_line=11382,
        text=(
            "Important test suites include negative controls or mutations that "
            "have been observed to FAIL."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11382]; CC-0014 / TST census "
            "_USER-PROMPTS.md:11382"
        ),
        spec={
            "kind": "all_have",
            "key": "suites",
            "field": "negative_control_observed_fail",
            "required_nonempty": True,
        },
        settling_probe=(
            "For each registered important suite, resolve its negative control "
            "to an executable artifact and record whether that control has ever "
            "been observed to FAIL."
        ),
        probe_cost=COST_SUITES,
    ),
    _absent(6, 11383),
    _p(
        id=7,
        spec_line=11384,
        text=(
            "Compatibility-matrix cells may only be marked supported by a "
            "recorded test run; an untested cell is NOT-CHECKED, never a pass."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor="ARC-0095 inputs cite _USER-PROMPTS.md:11384",
        spec={
            "kind": "cells_supported_only_with_run",
            "key": "compatibility_cells",
            "required_nonempty": True,
        },
        settling_probe=(
            "Generate the compatibility matrix from recorded test runs; a "
            "SUPPORTED cell without a test_run pointer is FALSE. Confirm "
            "verbatim spec line 11384 when _USER-PROMPTS.md is present."
        ),
        probe_cost=COST_MATRIX,
    ),
    _p(
        id=8,
        spec_line=11385,
        text="Intended improvement without material regression.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11385]; TST-0324 / SYN units "
            "_USER-PROMPTS.md:11385"
        ),
        spec={"kind": "benchmark", "key": "benchmark"},
        settling_probe=(
            "TST-0324: function over the results ledger, B07 margin table and "
            "B04 intervals with run ids attached. Missing data is NOT-CHECKED."
        ),
        probe_cost=COST_BENCH,
    ),
    _absent(9, 11386),
    _absent(10, 11387),
    _p(
        id=11,
        spec_line=11388,
        text=(
            "Release-time re-execution of vulnerability and license scanners "
            "(a stored implementation-time scan does not satisfy)."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor="ADV-0016 spec_anchor _USER-PROMPTS.md:11112, 11129, 11388",
        spec={
            "kind": "all_of",
            "parts": [
                {"kind": "bool", "key": "vuln_scan_fresh"},
                {"kind": "bool", "key": "license_scan_fresh"},
            ],
        },
        settling_probe=(
            "Re-run vuln and license scanners at release/merge-candidate time "
            "and compare timestamps to implementation-time scans. Confirm "
            "verbatim spec line 11388 when _USER-PROMPTS.md is present."
        ),
        probe_cost=COST_SCAN,
    ),
    _p(
        id=12,
        spec_line=11389,
        text="Docs and code agree.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11389]; ARC-0106 / ADV-0112 "
            "_USER-PROMPTS.md:11389"
        ),
        spec={"kind": "bool", "key": "docs_code_agree"},
        settling_probe=(
            "Diff documented commands and behaviour statements against measured "
            "behaviour (SYN-0034 / docs-code gate). A missing measurement is "
            "NOT-CHECKED."
        ),
        probe_cost=COST_EXTRACT,
    ),
    _p(
        id=13,
        spec_line=11390,
        text=SC13_AS_WRITTEN,
        text_confidence="QUOTED",
        catalog_anchor=(
            "ARC-0097 / REL-0003 / CC-0015: stop condition 13, spec 11390, "
            "'release/canary succeeds'"
        ),
        spec=SC13_AS_WRITTEN_SPEC,
        settling_probe=(
            "As written: observe a canary or marketplace release succeeding. "
            "Under PR-ONLY those referents do not exist. Amended (REL-0003): "
            "merged PR plus green REL-0004/REL-0005/REL-0006 receipts."
        ),
        probe_cost=COST_LOCAL,
        as_written_satisfiability="UNSATISFIABLE-AS-WRITTEN",
        as_written_text=SC13_AS_WRITTEN,
        amendment={
            "ruling_id": "REL-0003",
            "text": SC13_AMENDED,
            "amended": SC13_AMENDED_SPEC,
        },
    ),
    _p(
        id=14,
        spec_line=11391,
        text="Rollback is tested.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 fixture line 11391; REL / ADV-0119 "
            "_USER-PROMPTS.md:11391 (rollback is tested)"
        ),
        spec={"kind": "bool", "key": "rollback_tested"},
        settling_probe=(
            "A recorded rollback/downgrade rehearsal (REL-0006 or equivalent) "
            "must exist and be green. Missing evidence is NOT-CHECKED."
        ),
        probe_cost=COST_LOCAL,
    ),
    _p(
        id=15,
        spec_line=11392,
        text=(
            "Every open unknown has a named settling experiment and an "
            "owner-visible impact statement."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11392]; AUD / SYN units "
            "_USER-PROMPTS.md:11392"
        ),
        spec={"kind": "unknowns_two_part", "key": "unknowns"},
        settling_probe=(
            "Reconcile UNKNOWNS-REGISTER.md against residual / UNVERIFIED / "
            "NOT-CHECKED tags; each open unknown needs both halves."
        ),
        probe_cost=COST_UNK,
    ),
    _p(
        id=16,
        spec_line=11393,
        text=(
            "At least 160 workflow candidates classified with provenance and "
            "licence records."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11393]; WFA-0123 "
            "_USER-PROMPTS.md:11393"
        ),
        spec={
            "kind": "count_ge",
            "key": "counts.workflow_candidates_classified",
            "floor": 160,
        },
        settling_probe=(
            "Independent extractor: count only rows that are classified AND "
            "have resolved provenance AND a fetched licence. Raw record count "
            "is not this floor."
        ),
        probe_cost=COST_EXTRACT,
    ),
    _p(
        id=17,
        spec_line=11394,
        text=(
            "At least 96 materially distinct workflow blueprints executable "
            "under the selected quality tiers."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11394]; WFA-0124 inputs "
            "_USER-PROMPTS.md:11394"
        ),
        spec={
            "kind": "count_ge",
            "key": "counts.blueprints_executable",
            "floor": 96,
        },
        settling_probe=(
            "Independent recount of executable, materially distinct blueprints "
            "under the selected quality tiers."
        ),
        probe_cost=COST_EXTRACT,
    ),
    _p(
        id=18,
        spec_line=11395,
        text="At least 48 council protocols remain distinct from presets.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11395]; SYN-0031 :11393-11396",
        spec={
            "kind": "all_of",
            "parts": [
                {
                    "kind": "count_ge",
                    "key": "counts.council_protocols",
                    "floor": 48,
                },
                {
                    "kind": "disjoint_ids",
                    "key_a": "protocol_ids",
                    "key_b": "preset_ids",
                },
            ],
        },
        settling_probe=(
            "Count council protocols and prove protocol ids intersect preset "
            "ids in the empty set."
        ),
        probe_cost=COST_EXTRACT,
    ),
    _p(
        id=19,
        spec_line=11396,
        text="At least 64 editable presets.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11396]; SYN-0031 :11393-11396",
        spec={"kind": "count_ge", "key": "counts.presets", "floor": 64},
        settling_probe="Independent recount of editable presets.",
        probe_cost=COST_EXTRACT,
    ),
    _absent(20, 11397),
    _absent(21, 11398),
]


def encodings() -> list[dict]:
    rows = list(ENCODINGS)
    if len(rows) != 21 or [r["id"] for r in rows] != list(range(1, 22)):
        raise RuntimeError("encodings are not 1..21")
    if [r["spec_line"] for r in rows] != list(range(11378, 11399)):
        raise RuntimeError("spec lines are not 11378-11398")
    return rows
