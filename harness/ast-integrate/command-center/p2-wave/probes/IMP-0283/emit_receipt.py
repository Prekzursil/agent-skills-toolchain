#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0283.json from a live PCJ run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import fixture as F  # noqa: E402
from tools.council.topology.pcj import (  # noqa: E402
    STAGES,
    fabricated_citation_control,
    kinds_of,
)

OUT_REL = "command-center/receipts/IMP-0283.json"
MODULE_REL = "tools/council/topology/pcj.py"
STARTED = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": "supporting",
    }


def build_receipt() -> dict:
    result = F.live_pipeline()
    census = result.census
    kinds = kinds_of(result)
    view_blob = json.dumps(result.view, sort_keys=True)
    genuine = [p["point_id"] for p in result.view["points"]]
    ctrl = fabricated_citation_control(
        result.view,
        genuine=genuine[:1],
        fabricated=F.FABRICATED_POINT_ID,
        judge_id=F.JUDGE_ID,
    )
    expected_kinds = ["pcj.proposal", "pcj.critique", "pcj.judge_view", "pcj.ruling"]
    if census["identity_leaked"] or F.PROPOSER_ID in view_blob:
        raise SystemExit("FAILED:IMP-0283 judge view leaked proposer identity")
    if census["unsurfaced_reasoning_in_view"] or F.UNSURFACED in view_blob:
        raise SystemExit("FAILED:IMP-0283 judge view leaked unsurfaced reasoning")
    if F.SURFACED not in view_blob:
        raise SystemExit("FAILED:IMP-0283 judge view missing surfaced excerpt")
    if not ctrl["silent_on_good_state"] or not ctrl["fired_on_bad_state"]:
        raise SystemExit(f"FAILED:IMP-0283 citation both-states {ctrl}")
    if kinds != expected_kinds:
        raise SystemExit(f"FAILED:IMP-0283 kinds {kinds}")
    if not result.citation_check.ok:
        raise SystemExit("FAILED:IMP-0283 live ruling failed citation check")

    supporting = [
        MODULE_REL,
        "tools/council/topology/__init__.py",
        "command-center/p2-wave/probes/IMP-0283/fixture.py",
        "command-center/p2-wave/probes/IMP-0283/probe1_staged_handoff.py",
        "command-center/p2-wave/probes/IMP-0283/probe2_fabricated_citations.py",
        "command-center/p2-wave/probes/IMP-0283/emit_receipt.py",
    ]
    artifacts = [digest(p) for p in supporting]
    artifacts[0]["role"] = "primary-module"
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": 1,
        "unit_id": "IMP-0283",
        "id": "IMP-0283",
        "title": "Proposer-critic-judge pipeline topology",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0283",
        "completion_sentinel": "SUCCESS:IMP-0283",
        "profile": "council-topology-module",
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0283 / CNL-0032 proposer-critic-judge "
            "pipeline; inputs _USER-PROMPTS.md:10915-10946 and 11-COUNCIL-SPECIFICATION.md"
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-topology-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], test_ids[], "
            "negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "min_bytes_threshold": 2048,
        "question_or_target": (
            "Implement tools/council/topology/pcj.py with three staged roles and "
            "typed handoff artifacts (proposal, critique, ruling). Falsifiable "
            "question: does the judge ever see the proposer's identity or reasoning "
            "that the critique did not surface, and can a judge rule without citing "
            "at least one critique point?"
        ),
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "Cursor Grok 4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
            "worktree": "/opt/p2/ast-integrate",
        },
        "artifact_paths": [OUT_REL, *supporting],
        "artifacts": artifacts,
        "evidence": [
            {
                "id": "E-JUDGE-CONTEXT-CENSUS",
                "claim": (
                    "Judge-view census after a live propose->critique->rule run: "
                    f"fields={census['field_names']} n_claims={census['n_claims']} "
                    f"n_points={census['n_points']} point_ids={census['point_ids']}. "
                    f"identity_leaked={census['identity_leaked']} "
                    f"proposer_id_field_present={census['proposer_id_field_present']} "
                    f"planted identity token {F.PROPOSER_ID!r} absent from the view. "
                    "Answer: the judge does not see proposer identity."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE_REL}:judge_view",
                "confidence": "almost-certain",
            },
            {
                "id": "E-UNSURFACED-REASONING-ABSENT",
                "claim": (
                    "Proposal.reasoning contains planted token "
                    f"{F.UNSURFACED!r}. Critique points surface {F.SURFACED!r} only. "
                    f"unsurfaced_reasoning_in_view={census['unsurfaced_reasoning_in_view']} "
                    f"reasoning_field_present={census['reasoning_field_present']} "
                    f"surfaced_excerpt_in_view={F.SURFACED in view_blob}. "
                    "Answer: unsurfaced proposer reasoning does not reach the judge; "
                    "that loss is the topology, not a defect."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0283/fixture.py:1",
                "confidence": "almost-certain",
            },
            {
                "id": "E-CITATION-RESOLVABILITY",
                "claim": (
                    "Citation check on the live ruling "
                    f"ok={result.citation_check.ok} cited={list(result.ruling.citations)}. "
                    f"Fabricated id {F.FABRICATED_POINT_ID!r}: "
                    f"bad_ok={ctrl['bad_ok']} unresolved={ctrl['unresolved']} "
                    f"issue_ruling_refused={ctrl['issue_ruling_refused_fabricated']}. "
                    f"Empty citations empty_ok={ctrl['empty_ok']}. "
                    "Answer: a judge cannot rule without citing at least one "
                    "resolvable critique-point id."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{MODULE_REL}:check_citations",
                "confidence": "almost-certain",
            },
        ],
        "test_ids": [
            "T-STAGED-TYPED-HANDOFF",
            "T-JUDGE-CONTEXT-CENSUS-NO-IDENTITY",
            "T-UNSURFACED-REASONING-ABSENT",
            "T-CITATION-RESOLVABILITY",
        ],
        "negative_control_ids": [
            "NC-FABRICATED-CRITIQUE-IDS-FAIL",
            "NC-EMPTY-CITATIONS-FAIL",
        ],
        "tests": [
            {
                "id": "T-STAGED-TYPED-HANDOFF",
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"kinds={kinds} stages={list(STAGES)}",
            },
            {
                "id": "T-JUDGE-CONTEXT-CENSUS-NO-IDENTITY",
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"identity_leaked={census['identity_leaked']} "
                    f"proposer_id_field_present={census['proposer_id_field_present']}"
                ),
            },
            {
                "id": "T-UNSURFACED-REASONING-ABSENT",
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"unsurfaced={census['unsurfaced_reasoning_in_view']} "
                    f"surfaced_excerpt={F.SURFACED in view_blob}"
                ),
            },
            {
                "id": "T-CITATION-RESOLVABILITY",
                "result": "PASS",
                "assertions": 3,
                "output_tail": (
                    f"live_ok={result.citation_check.ok} "
                    f"fabricated_ok={ctrl['bad_ok']} empty_ok={ctrl['empty_ok']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-FABRICATED-CRITIQUE-IDS-FAIL",
                "kind": "known-broken-fixture",
                "description": (
                    "A ruling that cites CP-FABRICATED-DOES-NOT-EXIST must FAIL "
                    "check_citations and be refused by issue_ruling."
                ),
                "fired_on_bad_state": ctrl["fired_on_bad_state"],
                "silent_on_good_state": ctrl["silent_on_good_state"],
                "good_state_output": f"good_ok={ctrl['good_ok']} cited={genuine[:1]}",
                "bad_state_output": (
                    f"bad_ok={ctrl['bad_ok']} reason={ctrl['bad_reason']} "
                    f"unresolved={ctrl['unresolved']}"
                ),
            },
            {
                "id": "NC-EMPTY-CITATIONS-FAIL",
                "kind": "known-broken-fixture",
                "description": "A ruling with zero citations must FAIL check_citations.",
                "fired_on_bad_state": not ctrl["empty_ok"],
                "silent_on_good_state": ctrl["good_ok"],
                "bad_state_output": (
                    f"empty_ok={ctrl['empty_ok']} reason={ctrl['empty_reason']}"
                ),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0283-probe2-fabricated-citations",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "tests (citation check both-states), not the author summary",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Isolation is a projection plus token redaction. A critic who "
                    "paraphrases proposer identity without using the planted token "
                    "would not be caught by the string census."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Add a paraphrase-identity arm: critic writes 'the author, Alice', "
                    "and require a structured identity field still be absent while "
                    "disclosing paraphrase as residual."
                ),
            },
            {
                "claim": (
                    "tools/council/kernel.py (IMP-0264) is not on this worktree. "
                    "The topology records a local handoff log; it does not claim "
                    "kernel event-loop wiring."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "When kernel.py exists, assert every PCJ stage is a kernel turn "
                    "and that a topology cannot write a ruling the citation checker "
                    "never sees."
                ),
            },
        ],
        "timestamps": {"started_at": STARTED, "ended_at": ended},
        "report": {
            "kind": "council-topology-pcj",
            "module": MODULE_REL,
            "kinds": kinds,
            "stages": list(STAGES),
            "census": {
                "n_claims": census["n_claims"],
                "n_points": census["n_points"],
                "point_ids": census["point_ids"],
                "identity_leaked": census["identity_leaked"],
                "unsurfaced_reasoning_in_view": census["unsurfaced_reasoning_in_view"],
                "field_names": census["field_names"],
            },
            "falsifiable_answers": {
                "judge_sees_proposer_identity": False,
                "judge_sees_unsurfaced_reasoning": False,
                "judge_can_rule_without_critique_citation": False,
            },
            "citation_control": {
                "good_ok": ctrl["good_ok"],
                "bad_ok": ctrl["bad_ok"],
                "empty_ok": ctrl["empty_ok"],
                "fabricated_id": F.FABRICATED_POINT_ID,
                "unresolved": ctrl["unresolved"],
                "issue_ruling_refused_fabricated": ctrl["issue_ruling_refused_fabricated"],
            },
        },
        "notes": (
            "G-1 delivery for IMP-0283: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not "
            "run tools/command-center/unit_manifest.py --write. Did not relaunch "
            "finish-everything-close or p2-cloud-ok-deliver. cloud ok=true is "
            "not this unit's delivery predicate."
        ),
    }


def write_receipt(doc: dict | None = None) -> Path:
    receipt = doc if doc is not None else build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0283" not in text:
        raise SystemExit("FAILED:IMP-0283 sentinel missing from serialised receipt")
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        raise SystemExit("FAILED:IMP-0283 state not SUCCESS")
    out.write_text(text, encoding="utf-8")
    return out


def main() -> int:
    path = write_receipt()
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    print(
        f"wrote {OUT_REL} bytes={len(raw)} "
        f"sha256={hashlib.sha256(raw).hexdigest()}"
    )
    print("SUCCESS:IMP-0283 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
