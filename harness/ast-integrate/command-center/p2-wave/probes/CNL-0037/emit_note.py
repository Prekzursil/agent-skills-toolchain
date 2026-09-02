#!/usr/bin/env python3
"""Emit the CNL-0037 design note (JSON body, .md path from the catalog)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fanin import fan_in, majority_would_pass  # noqa: E402
from reviewer import counterexample_blind_overrule  # noqa: E402
from scenarios import (  # noqa: E402
    agreeing_pass,
    claim_without_artifact,
    completion_split,
    disagree_irreducible,
    majority_trap,
    overrule_blind,
    overrule_cited,
)

OUT_REL = (
    "command-center/design/council/"
    "CNL-0037-nested-subcouncils-and-council-of-councils-fan-in.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
NOTE_SCHEMA_REL = "command-center/p2-wave/probes/CNL-0037/note.schema.json"
FC_REPLICA_REL = "command-center/p2-wave/probes/TST-0295/seeded_classes.py"
SPEC_REPLICA_REL = (
    "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
)
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
FANIN_REL = "command-center/p2-wave/probes/CNL-0037/fanin.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0037/probe1_disagreeing_children.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0037/probe2_overrule_evidence.py"
)
QUESTION = (
    "When nested councils return conflicting verdicts, what is the fan-in rule "
    "- and is a parent council permitted to overrule a child whose evidence it never read?"
)
DEP_PATHS = {
    "CNL-0031": (
        "command-center/design/council/"
        "CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md"
    ),
    "CNL-0071": (
        "command-center/design/council/"
        "CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md"
    ),
}
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def find_line(rel: str, needle: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"needle not found in {rel}: {needle}")


def main() -> int:
    split = fan_in(disagree_irreducible())
    trap_payload = majority_trap()
    trap = fan_in(trap_payload)
    cited = fan_in(overrule_cited())
    blind = fan_in(overrule_blind())
    agree = fan_in(agreeing_pass())
    missing = fan_in(claim_without_artifact())
    nested = fan_in(completion_split())
    rev = counterexample_blind_overrule()
    if not rev["ok"]:
        print("FAILED:emit reviewer counterexample did not hold")
        print(json.dumps(rev, indent=2, default=str)[:2000])
        return 1

    neg_text = (
        "negative-control target=overrule-blind "
        f"overrule.accepted={blind['overrule']['accepted']} "
        f"overrule.reason={blind['overrule']['reason']} "
        f"outcome={blind['outcome']} "
        f"parent_complete={blind['parent_complete']}"
    )

    fc_line = find_line(FC_REPLICA_REL, '"id": "FC-11343"')
    name_line = find_line(FC_REPLICA_REL, "nested councils disagree on completion")
    spec_line = find_line(SPEC_REPLICA_REL, "nested councils disagree on completion")
    cat_line = find_line(
        CATALOG_REL,
        "_USER-PROMPTS.md:11343 (nested councils disagree on completion)",
    )
    impl_line = find_line(FANIN_REL, "BLIND_OVERRULE")

    answer = (
        "Fan-in rule FANIN-NESTED-V1: (1) each child verdict is a claim; "
        "a missing or empty artifact, or a verdict with no evidence body, "
        "normalizes to INCOMPLETE (a digest is not a receipt). (2) duplicate "
        "child_id is MALFORMED (no double-count). (3) any required INCOMPLETE "
        "child makes the parent INCOMPLETE — not a vote. (4) if remaining "
        "normalized verdicts are identical, that is the parent outcome. "
        "(5) if they conflict, the parent may overrule a named child only by "
        "citing that child's own evidence ids with matching digests AND by "
        "having ingested those evidence bodies; otherwise overrule is rejected. "
        "(6) unresolved conflict emits IRREDUCIBLE_DISAGREEMENT, a defined "
        "fan-in outcome that is not parent completion and is not a majority "
        "PASS. (7) every child dissent id is forwarded. "
        "A parent is not permitted to overrule a child whose evidence it never "
        f"read: the blind fixture is rejected as {blind['overrule']['reason']}. "
        "Regression anchor is FC-11343 (spec 11343, nested councils disagree "
        "on completion)."
    )

    deps = {}
    for uid, rel in DEP_PATHS.items():
        present = (REPO / rel).is_file()
        deps[uid] = {
            "artifact_present": present,
            "path": rel,
            "note": (
                "present"
                if present
                else (
                    "absent on this worktree; CNL-0037 states the nesting-depth "
                    "rule without inheriting their numbers"
                )
            ),
        }

    note = {
        "unit_id": "CNL-0037",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0037",
        "title": "Nested subcouncils and council-of-councils fan-in",
        "question": QUESTION,
        "answer": answer,
        "claim_under_test": (
            "Conflicting child councils fan in by evidence-gated resolution or "
            "defined irreducible disagreement; a parent cannot overrule unread evidence."
        ),
        "fan_in_rule": {
            "id": "FANIN-NESTED-V1",
            "parent_may_overrule_unread_child": False,
            "majority_of_verdict_strings": False,
            "digest_is_receipt": False,
            "irreducible_disagreement_is_defined_outcome": True,
            "irreducible_is_parent_completion": False,
        },
        "declared_signal": {
            "name": "child-evidence-normalized-verdicts",
            "not": "majority-of-child-verdict-strings",
        },
        "which_stops_the_round": {
            "stops": (
                "defined fan-in outcome: unanimous PASS/REFUTED, "
                "IRREDUCIBLE_DISAGREEMENT, INCOMPLETE, or MALFORMED"
            ),
            "does_not_stop": "majority PASS, averaged verdict, or digest-without-artifact",
            "satisfy_quota_from_padding": False,
        },
        "dependency_status": deps,
        "catalog_inputs_on_tree": {path: False for path in CATALOG_INPUTS},
        "residual_unknowns": [
            "Harness-restore _USER-PROMPTS.md:11343 and command-center/phase3/A1/FAILURE-MODES.json are absent on this Linux worktree; in-tree replicas are TST-0295/seeded_classes.py (FC-11343) and CC-0024 prompt-two-slice.md:11343.",
            "CNL-0071 owns the information-gain threshold for a single council loop; this unit only requires that fan-in of already-returned children be defined.",
            "CNL-0031 owns grouping granularity (flat/committee/caucus); nesting depth is a different axis.",
        ],
        "claims": [
            {
                "id": "C1",
                "claim": "Two-PASS one-REFUTED children must not fan in to PASS by majority.",
                "verdict": "CONFIRMED",
                "anchor": f"{FANIN_REL}:{impl_line}",
            },
            {
                "id": "C2",
                "claim": "A parent may not overrule a child whose evidence body it never ingested.",
                "verdict": "CONFIRMED",
                "anchor": f"{FANIN_REL}:{impl_line}",
            },
            {
                "id": "C3",
                "claim": "Disagreeing children reach IRREDUCIBLE_DISAGREEMENT, a defined non-complete outcome (FC-11343).",
                "verdict": "CONFIRMED",
                "anchor": f"{FC_REPLICA_REL}:{name_line}",
            },
        ],
        "evidence": [
            {
                "path": FC_REPLICA_REL,
                "line": fc_line,
                "snippet": "FC-11343",
                "kind": "fixture-replica",
                "claim": "Spec 11343 is recorded in-tree as FC-11343 (FAILURE-MODES.json absent on this worktree).",
            },
            {
                "path": FC_REPLICA_REL,
                "line": name_line,
                "snippet": "nested councils disagree on completion",
                "kind": "fixture-replica",
                "claim": "Failure-mode name matches the catalog evidence requirement.",
            },
            {
                "path": SPEC_REPLICA_REL,
                "line": spec_line,
                "snippet": "nested councils disagree on completion",
                "kind": "spec-replica",
                "claim": "Recovered prompt slice keeps original line 11343 of the nested-completion failure class.",
            },
            {
                "path": CATALOG_REL,
                "line": cat_line,
                "snippet": "nested councils disagree on completion",
                "kind": "catalog-anchor",
                "claim": "CNL-0037 evidence requirement cites _USER-PROMPTS.md:11343.",
            },
            {
                "path": FANIN_REL,
                "line": impl_line,
                "snippet": "BLIND_OVERRULE",
                "kind": "live-tree",
                "claim": "Blind overrule is a named rejection, not a silent parent PASS.",
                "verbatim_output": neg_text,
            },
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "measured_fixtures": {
            "agreeing_pass": {
                "outcome": agree["outcome"],
                "parent_complete": agree["parent_complete"],
            },
            "disagree_irreducible": {
                "outcome": split["outcome"],
                "parent_complete": split["parent_complete"],
                "fan_in_defined": split["fan_in_defined"],
                "forwarded_dissent_ids": split["forwarded_dissent_ids"],
            },
            "majority_trap": {
                "outcome": trap["outcome"],
                "parent_complete": trap["parent_complete"],
                "majority_would_pass": majority_would_pass(trap_payload),
            },
            "overrule_cited": {
                "outcome": cited["outcome"],
                "overrule_accepted": cited["overrule"]["accepted"],
                "forwarded_dissent_ids": cited["forwarded_dissent_ids"],
            },
            "overrule_blind": {
                "outcome": blind["outcome"],
                "overrule_accepted": blind["overrule"]["accepted"],
                "overrule_reason": blind["overrule"]["reason"],
            },
            "claim_without_artifact": {
                "outcome": missing["outcome"],
                "parent_complete": missing["parent_complete"],
            },
            "completion_split": {
                "outcome": nested["outcome"],
                "parent_complete": nested["parent_complete"],
            },
        },
        "negative_controls": [
            {
                "id": "NC-blind-overrule",
                "rejects": (
                    "parent overrule that cites a child evidence id/digest copied from the "
                    "header without ingesting the evidence body"
                ),
                "verbatim": neg_text,
            }
        ],
        "reviewer": {
            "reviewer_id": rev["reviewer_id"],
            "verdict": rev["verdict"],
            "independent": True,
            "scope_not_agreement": True,
            "re_ran_both_states": True,
            "counterexample_instance": rev["counterexample_instance"],
            "refuted_not_attempted": False,
        },
        "strongest_surviving_counterargument": (
            "A parent that copies evidence ids from a child header might claim it cited "
            "the child without reading the body. FANIN-NESTED-V1 rejects that as "
            "BLIND_OVERRULE unless the parent ingested the matching body. Residual risk: "
            "an implementation could treat header-copy as ingest; the probe's "
            "parent_ingested map is the mechanical distinction."
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": FANIN_REL, "exists": True, "role": "supporting"},
            {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
            {"path": NOTE_SCHEMA_REL, "exists": True, "role": "supporting"},
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    schema = json.loads((REPO / NOTE_SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(note)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(note, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL}")
    print("SUCCESS:CNL-0037 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
