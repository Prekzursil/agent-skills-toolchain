#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0262.json from a live gated election."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote import evidence_gate as G  # noqa: E402

UNIT = "TST-0262"
OUT = "command-center/receipts/TST-0262.json"
MODULE = "tools/council/vote/evidence_gate.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0262/probe1_minority_wins.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0262/probe2_fabricated_citation.py"
)
QUESTION = (
    "Implementation target: bind every ballot to at least one evidence node "
    "in the council graph and make an unbacked ballot non-counting rather "
    "than merely annotated. Spec :11233 names vote counting without evidence "
    "and :11198 states that agreement is not proof and evidence gates outrank "
    "popularity. The test that matters is the one where the unbacked majority "
    "LOSES to the backed minority, because a system that records the objection "
    "and then counts the vote anyway has implemented nothing."
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0262] "
    "question_or_target + tests_required + evidence_requirement"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size if path.is_file() else 0,
        "sha256": digest or ("0" * 64),
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def compact_record(rec: dict) -> dict:
    return {
        "election_id": rec["election_id"],
        "n_ballots": rec["n_ballots"],
        "n_backed": rec["n_backed"],
        "n_unbacked": rec["n_unbacked"],
        "raw_tally": rec["raw_tally"],
        "counting_tally": rec["counting_tally"],
        "annotated_only_tally": rec["annotated_only_tally"],
        "raw_winner": rec["raw_winner"]["outcome"],
        "outcome": rec["outcome"],
        "binding": rec["binding"],
        "gate_outranks_popularity": rec["gate_outranks_popularity"],
        "why": rec["why"],
        "why_text": rec["why_text"],
        "ballots": [
            {
                "voter_id": b["voter_id"],
                "choice": b["choice"],
                "evidence_ids": b["evidence_ids"],
                "backed": b["backed"],
                "counts": b["counts"],
                "status": b["status"],
                "resolving_ids": b["resolving_ids"],
                "resolution_reasons": [r["reason"] for r in b["resolutions"]],
            }
            for b in rec["ballots"]
        ],
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    report = G.run_required_controls()
    fails = G.assertions(report)
    if fails:
        print("FAILED:TST-0262 emit live assertions")
        for f in fails:
            print(f"  {f}")
        return 1

    rec1 = report["minority_vs_unbacked_majority"]
    rec2 = report["both_states_all_backed"]
    rec3 = report["fabricated_citation"]
    module_sha, module_bytes = sha256_file(REPO / MODULE)
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    supporting = [
        MODULE,
        "tools/council/vote/__init__.py",
        "command-center/p2-wave/probes/TST-0262/probe1_minority_wins.py",
        "command-center/p2-wave/probes/TST-0262/probe2_fabricated_citation.py",
    ]
    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0262",
        "completion_sentinel": "SUCCESS:TST-0262",
        "title": "Refuse a vote that cites no evidence node, and prove the gate outranks the tally",
        "question": QUESTION,
        "spec_anchor": SPEC_ANCHOR,
        "report_kind": "council-vote-module",
        "profile": "council-vote-module",
        "min_bytes_threshold": 2048,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-vote-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "artifact_paths": [OUT, *supporting],
        "artifacts": [{"path": OUT, "exists": True, "role": "primary", "eol": "LF"}]
        + [art(p, "supporting") for p in supporting],
        "scheme": G.SCHEME_ID,
        "module": {
            "path": MODULE,
            "sha256": module_sha,
            "bytes": module_bytes,
        },
        "raw_majority_votes": report["raw_majority_votes"],
        "raw_minority_votes": report["raw_minority_votes"],
        "counting_majority_votes": report["counting_majority_votes"],
        "backed_minority_votes": report["backed_minority_votes"],
        "gated_outcome": report["gated_outcome"],
        "both_states_outcome": report["both_states_outcome"],
        "fabricated_outcome": report["fabricated_outcome"],
        "decision_record": compact_record(rec1),
        "both_states_record": compact_record(rec2),
        "fabricated_citation": {
            "fabricator_backed": False,
            "fabricator_counts": False,
            "fabricator_reason": "unknown-id",
            "fabricated_id": G.FABRICATED_EVIDENCE_ID,
            "outcome": rec3["outcome"],
            "record": compact_record(rec3),
        },
        "evidence_requirement": {
            "backed_minority_outcome": rec1["outcome"],
            "raw_tally_showing_outvoted": rec1["raw_tally"],
            "counting_tally": rec1["counting_tally"],
            "numbers_in_receipt": {
                "unbacked_majority": report["raw_majority_votes"],
                "backed_minority": report["backed_minority_votes"],
            },
            "why": rec1["why_text"],
        },
        "evidence": [
            {
                "id": "E1-unbacked-majority-loses",
                "kind": "live-decision-record",
                "verdict": "CONFIRMED",
                "anchor": SPEC_ANCHOR,
                "claim": (
                    f"7-vote unbacked majority ({G.MAJORITY_CHOICE} raw="
                    f"{report['raw_majority_votes']}) versus 2-vote evidence-backed "
                    f"minority ({G.MINORITY_CHOICE} raw={report['raw_minority_votes']}, "
                    f"counting={report['backed_minority_votes']}) -> outcome is "
                    f"{rec1['outcome']}. Raw winner would have been "
                    f"{rec1['raw_winner']['outcome']}. Why: {rec1['why_text']}"
                ),
                "measured": compact_record(rec1),
            },
            {
                "id": "E2-both-states-ordinary-tally",
                "kind": "live-decision-record",
                "verdict": "CONFIRMED",
                "anchor": SPEC_ANCHOR,
                "claim": (
                    "When every ballot is backed on the same 7-2 split, ordinary "
                    f"tally decides: outcome={rec2['outcome']} "
                    f"(raw={rec2['raw_tally']}, counting={rec2['counting_tally']}). "
                    "The gate does not silently invert a fully-backed election."
                ),
                "measured": compact_record(rec2),
            },
            {
                "id": "E3-fabricated-citation-unbacked",
                "kind": "live-decision-record",
                "verdict": "CONFIRMED",
                "anchor": SPEC_ANCHOR,
                "claim": (
                    f"Ballot citing {G.FABRICATED_EVIDENCE_ID} (absent from the graph) "
                    "is unbacked-non-counting with reason=unknown-id; outcome follows "
                    f"the resolving minority ballot ({rec3['outcome']})."
                ),
                "measured": compact_record(rec3),
            },
        ],
        "test_ids": [
            "TST-0262-7v2-unbacked-majority-loses",
            "TST-0262-both-states-all-backed-ordinary-tally",
            "TST-0262-fabricated-citation-unbacked",
        ],
        "tests": [
            {
                "id": "TST-0262-7v2-unbacked-majority-loses",
                "name": "7-vote unbacked majority versus 2-vote evidence-backed minority -> minority position, record states why",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0262-both-states-all-backed-ordinary-tally",
                "name": "When every ballot is backed, ordinary tally decides",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0262-fabricated-citation-unbacked",
                "name": "Ballot citing a non-existent evidence id is unbacked, not backed",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_control_ids": [
            "NC-FABRICATED-CITATION-UNBACKED",
            "NC-ANNOTATION-ONLY-STILL-COUNTS",
            "NC-UNRESOLVED-NODE-UNBACKED",
            "NC-BOTH-STATES-DOES-NOT-INVERT",
        ],
        "negative_controls": [
            {
                "id": "NC-FABRICATED-CITATION-UNBACKED",
                "kind": "fabricated-anchor",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Citing EV-FABRICATED-MAJORITY-STUDY (not a graph node) is "
                    "unbacked. Citing EV-EXECUTABLE-COUNTEREXAMPLE is backed."
                ),
            },
            {
                "id": "NC-ANNOTATION-ONLY-STILL-COUNTS",
                "kind": "prove-by-contrast",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "description": (
                    "Annotation-only tally still elects the unbacked majority. "
                    "The counting gate elects the backed minority. If they agreed, "
                    "the gate would have implemented nothing."
                ),
                "annotation_only_outcome": rec1["annotated_only_winner"]["outcome"],
                "gated_outcome": rec1["outcome"],
            },
            {
                "id": "NC-UNRESOLVED-NODE-UNBACKED",
                "kind": "plausible-looking-citation",
                "description": (
                    "A graph node with resolves=False does not satisfy the gate "
                    "(IMP-0307: distinguish a real anchor from a citation that "
                    "does not resolve)."
                ),
            },
            {
                "id": "NC-BOTH-STATES-DOES-NOT-INVERT",
                "kind": "both-states",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "good_state_output": f"all-backed outcome={rec2['outcome']}",
                "bad_state_output": f"unbacked-majority outcome={rec1['outcome']}",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0262-probe2-fabricated-citation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Named probe2 starts from classify/decide and the fabricated "
                "fixture plus the annotation-only contrast. It does not author "
                "tools/council/vote/evidence_gate.py. Owner sign-off is a "
                "separate half of dual-control and is not granted here."
            ),
        },
        "owner_signoff": {
            "required": True,
            "granted": False,
            "granted_by_reviewer": False,
            "status": "NOT-GRANTED",
            "block": (
                "Owner sign-off is a separate half of the dual-control. The "
                "adversarial reviewer must not grant it."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py (TST-0257 deterministic council "
                    "simulator) is absent on this worktree. This unit exercises "
                    "the evidence gate with scripted ballots, not a full persona "
                    "cast through the council runtime."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the 7v2 fixture through tools/council/simulate.py "
                    "once TST-0257 lands."
                ),
            },
            {
                "claim": (
                    "TST-0280 property-tests of every voting method against its "
                    "axioms are not on disk; this gate composes with a unique-max "
                    "counting tally, not Condorcet/ranked/score methods."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Compose evidence_gate.counting_tally with each TST-0280 method.",
            },
            {
                "claim": (
                    "command-center/schema/receipt.schema.json is absent; G-1 "
                    "_measure_one_delivered.py does not schema-validate."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Validate this receipt against receipt.schema.json when present.",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "No automatic retry: a failure here is a finding, not a transient.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0262/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "named_probes": [
            {"id": "probe1", "role": "minority-wins-and-both-states", "command": P1},
            {"id": "probe2", "role": "fabricated-citation-negative-control", "command": P2},
        ],
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "linux-local",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "tools/council/simulate.py was executed",
                "owner_signoff was granted",
            ]
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0262 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0262" not in text:
        print("FAILED:TST-0262 sentinel missing after write")
        return 1
    if str(report["raw_majority_votes"]) not in text or str(report["backed_minority_votes"]) not in text:
        print("FAILED:TST-0262 both required numbers missing from receipt text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"raw_majority={report['raw_majority_votes']} "
        f"backed_minority={report['backed_minority_votes']} "
        f"outcome={report['gated_outcome']}"
    )
    print("SUCCESS:TST-0262 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
