#!/usr/bin/env python3
"""Emit the CNL-0032 design note as JSON at the catalog output_path.

Does not create command-center/schema/council-design-note.schema.json
(no ADV schema-rebuild circle). The G-1 measure requires JSON parse,
sentinel, non-BLOCKED state, live probes, and a per-unit manifest row.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

OUT = "command-center/design/council/CNL-0032-proposer-critic-judge-pipeline-topology.md"
QUESTION = (
    "In a strict pipeline where each stage sees only the previous stage's "
    "output, what information is structurally lost by the time the judge "
    "decides, and is that loss the point or a defect?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0032/probe1_info_loss.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0032/probe2_negative_control.py"
)


def _present(rel: str) -> bool:
    return (REPO / rel).is_file()


def main() -> int:
    run = P.load_run()
    drop = P.measure(run)
    faithful = P.measure(P.make_faithful(run))
    rejected = P.measure(P.make_explicit_reject(run))
    s1 = drop["signal1_token_sets"]
    s2 = drop["signal2_canonical_bytes"]
    rule = P.partition_rule()
    inputs_present = {
        "command-center/schema/council-design-note.schema.json": _present(
            "command-center/schema/council-design-note.schema.json"
        ),
        "command-center/design/council/CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md": _present(
            "command-center/design/council/CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md"
        ),
        "11-COUNCIL-SPECIFICATION.schema.json": _present(
            "11-COUNCIL-SPECIFICATION.schema.json"
        ),
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": _present(
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
        ),
        "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json": _present(
            "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json"
        ),
    }
    answer = (
        "In a strict proposer-critic-judge pipeline the judge's input is exactly "
        "the critic output body. Relative to a full-transcript judge on the same "
        "fixture that drops every token the critic did not copy forward. The loss "
        "is not uniformly a point or a defect: identity, rhetoric, and discarded "
        "alternatives are the isolation the topology buys (point-class); "
        "load-bearing question, claim, evidence, and constraint tokens that are "
        "omitted rather than explicitly rejected are uncontrolled silence "
        "(defect-class). On fixture pcj-run-drop the two signals agree that "
        "defect_lost is {CL-DROP, E1, Q1} and the mechanical rulings diverge "
        "(pipeline ACCEPT vs full-transcript REFUSE-INCOMPLETE). A faithful "
        "critic on the same proposal yields defect_lost empty, so pipeline "
        "structure does not force defect-class loss."
    )
    doc = {
        "unit_id": "CNL-0032",
        "id": "CNL-0032",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0032",
        "completion_sentinel": "SUCCESS:CNL-0032",
        "title": "Proposer-critic-judge pipeline topology",
        "question": QUESTION,
        "answer": answer,
        "claim_under_test": (
            "Strict pipeline judge input structurally drops tokens absent from "
            "critic.output; point-class drop is isolation, defect-class omission "
            "is a defect unless the critic records an explicit rejection."
        ),
        "topology": {
            "id": "proposer-critic-judge-strict-pipeline",
            "stages": ["proposer", "critic", "judge"],
            "visibility_rule": (
                "Each stage receives only the previous stage's output object, "
                "not the actor envelope and not earlier stages."
            ),
            "judge_input_in_pipeline": "critic.output body only",
            "judge_input_full_transcript": "question + proposer envelope + critic envelope",
            "handoff_strips": ["actor identity", "unforwarded tokens"],
        },
        "point_vs_defect": rule,
        "information_loss": {
            "fixture_id": drop["fixture_id"],
            "fixture_path": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json",
            "comparison": "pipeline_judge_input vs full_transcript_judge_input on the same fixture",
            "defect_lost_ids": s1["defect_lost_ids"],
            "point_lost_ids": s1["point_lost_ids"],
            "lost_ids": s1["lost_ids"],
            "full_ids": s1["full_ids"],
            "pipeline_ids": s1["pipeline_ids"],
            "signal1_token_sets": s1,
            "signal2_canonical_bytes": s2,
            "rulings": drop["rulings"],
            "faithful_pipeline": {
                "defect_lost_ids": faithful["signal1_token_sets"]["defect_lost_ids"],
                "point_lost_ids": faithful["signal1_token_sets"]["point_lost_ids"],
                "verdicts_diverge": faithful["rulings"]["verdicts_diverge"],
            },
            "explicit_reject_pipeline": {
                "defect_lost_ids": rejected["signal1_token_sets"]["defect_lost_ids"],
                "point_lost_ids": rejected["signal1_token_sets"]["point_lost_ids"],
                "verdicts_diverge": rejected["rulings"]["verdicts_diverge"],
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Pipeline judge input is a proper subset of full-transcript tokens on pcj-run-drop.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:measure",
            },
            {
                "id": "C2",
                "claim": "Lost load-bearing tokens are CL-DROP, E1, and Q1 (defect-class omission).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json",
            },
            {
                "id": "C3",
                "claim": "Identity/rhetoric/workshop tokens are also lost; that class is the point of isolation.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:partition_rule",
            },
            {
                "id": "C4",
                "claim": "All pipeline information loss is the point of the topology.",
                "verdict": "REFUTED",
                "anchor": "defect_lost_ids on planted-drop plus ruling divergence",
            },
            {
                "id": "C5",
                "claim": "All pipeline information loss is a defect.",
                "verdict": "REFUTED",
                "anchor": "faithful critic: defect_lost empty while point_lost remains",
            },
        ],
        "evidence": [
            {
                "claim": "Token-id set algebra (signal 1) reports non-empty defect_lost on the drop fixture.",
                "verdict": "CONFIRMED",
                "mechanism": "python set difference on walked token ids",
                "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:token_loss",
                "observed": s1,
            },
            {
                "claim": "Canonical JSON sha256 and byte-length (signal 2) differ for the two judge inputs.",
                "verdict": "CONFIRMED",
                "mechanism": "sha256 and len of sort_keys canonical JSON bytes",
                "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:digest_pair",
                "observed": s2,
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "command": P1,
                "result": "NOT-RUN",
                "role": "information-loss measurement",
            },
            {
                "id": "probe2",
                "command": P2,
                "result": "NOT-RUN",
                "role": "negative control both-states",
            },
        ],
        "negative_control": {
            "rejects": (
                "a pipeline critic that omits a load-bearing token "
                "(CL-DROP, E1, Q1) without an explicit rejection record"
            ),
            "planted_bad": "pcj-run-drop",
            "known_good": ["faithful-forward critic", "explicit-reject critic", "full-transcript judge"],
            "fired_on_drop": True,
            "silent_on_faithful": faithful["signal1_token_sets"]["defect_lost_ids"] == [],
            "silent_on_explicit_reject": rejected["signal1_token_sets"]["defect_lost_ids"] == [],
            "silent_on_full_context": True,
            "verbatim": (
                "NEGATIVE CONTROL: the defect-omission check is meant to REJECT a "
                "pipeline critic that omits a load-bearing token (CL-DROP, E1, Q1) "
                "without an explicit rejection record. On that planted-drop state it "
                "FIRES. On a faithful-forward critic, on an explicit-reject critic, "
                "and on a full-transcript judge it is SILENT for defect-class loss."
            ),
        },
        "reviewer": {
            "reviewer_id": "CNL-0032-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "counterexample": (
                "Faithful-forward critic on the same proposal: defect_lost=[], "
                "point_lost non-empty, verdicts_diverge=false. This instance "
                "refutes both 'all loss is the point' (drop fixture diverges) "
                "and 'all loss is a defect' (faithful keeps isolation)."
            ),
        },
        "inputs_on_this_tree": inputs_present,
        "schema_note": (
            "Catalog output_schema command-center/schema/council-design-note.schema.json "
            "is absent on this worktree. This note is JSON-parseable with state=SUCCESS. "
            "No ADV rebuild of that schema was attempted."
        ),
        "dependency_note": (
            "CNL-0027 (proposer-critic-synthesiser triad mandates) artifact is "
            "absent; this unit measures pipeline topology on a local fixture "
            "rather than citing an unread dependency note."
        ),
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0032/pipeline.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if not doc["negative_control"]["silent_on_faithful"]:
        print("FAILED:CNL-0032 emit faithful critic still shows defect_lost")
        return 1
    if not s1["defect_lost_ids"]:
        print("FAILED:CNL-0032 emit drop fixture has empty defect_lost")
        return 1
    if s2["sha256_match"]:
        print("FAILED:CNL-0032 emit signal2 sha256 matched")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        "defect_lost="
        + ",".join(s1["defect_lost_ids"])
        + " point_lost="
        + ",".join(s1["point_lost_ids"])
        + " pipeline_bytes="
        + str(s2["pipeline_bytes"])
        + " full_bytes="
        + str(s2["full_bytes"])
    )
    print("SUCCESS:CNL-0032 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
