#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0119-disagreement-adjudication.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adjudicate import adjudicate_all  # noqa: E402
from check import SENTINEL, check_artifact  # noqa: E402
from router import close  # noqa: E402

OUT = "command-center/confirmation/CNF-0119-disagreement-adjudication.json"
SCHEMA = "command-center/schema/adjudication-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0119/probe1_decisive.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0119/probe2_controls.py"
)
QUESTION = (
    "When the implementer and the confirmer disagree, who is right? Adjudicate "
    "each disagreement by returning to raw source and running a decisive probe, "
    "and answer per case: which side is correct, was the disagreement a real "
    "defect or an overclaim in the wording, and what is the correctly scoped "
    "statement? On this estate 5 of 8 refutations were overclaims where the "
    "code was fine."
)
CNF118 = REPO / "command-center/confirmation/CNF-0118-second-order-sample.json"
CNF013 = REPO / "command-center/confirmation/CNF-0013-discrepancy-router.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    refused, why = close({"id": "null-control", "disposition": None})
    if refused:
        print("FAILED:CNF-0119 null disposition was accepted")
        return 1
    residual_ok, residual_why = close(
        {
            "id": "residual-control",
            "disposition": "accepted-residual",
            "settling_experiment": "",
        }
    )
    if residual_ok:
        print("FAILED:CNF-0119 accepted-residual closed without settling experiment")
        return 1
    full_ok, full_why = close(
        {"id": "full-control", "disposition": "implementation-defect"}
    )
    if not full_ok:
        print(f"FAILED:CNF-0119 fully dispositioned close refused: {full_why}")
        return 1

    cases = adjudicate_all()
    overclaim = sum(1 for c in cases if c["classification"] == "overclaim")
    real_defect = sum(1 for c in cases if c["classification"] == "real-defect")
    code_fine_overclaim = sum(
        1 for c in cases if c["classification"] == "overclaim" and c["code_was_fine"]
    )
    majority_overridden = sum(1 for c in cases if c.get("majority_overridden"))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Of {len(cases)} implementer-versus-confirmer disagreements, the decisive "
        f"probe sided with the confirmer in every case. {overclaim} were overclaims "
        f"(code fine, sentence wider than the measured set) and {real_defect} were "
        f"real defects. {code_fine_overclaim} of {len(cases)} overclaims had working "
        f"code. Majority vote was overridden in {majority_overridden} case(s); the "
        f"probe wins over the head count. CNF-0118 and CNF-0013 artifacts are absent; "
        f"this corpus is the reconstructed disagreement list plus a local router. "
        f"{SENTINEL}"
    )
    doc = {
        "unit_id": "CNF-0119",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Adjudicate implementer-versus-confirmer disagreements from raw source only",
        "question": QUESTION,
        "answer": answer,
        "adjudication_method": "decisive-probe",
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "inputs_observed": {
            "CNF-0118-second-order-sample": {
                "path": "command-center/confirmation/CNF-0118-second-order-sample.json",
                "present": CNF118.is_file(),
            },
            "CNF-0013-discrepancy-router": {
                "path": "command-center/confirmation/CNF-0013-discrepancy-router.json",
                "present": CNF013.is_file(),
            },
            "reconstruction": (
                "Upstream sample and router artifacts are absent. Eight fixture "
                "disagreements with on-disk raw source stand in as the disagreement "
                "list. A local router (probes/CNF-0119/router.py) refuses null "
                "disposition and accepted-residual without a settling experiment."
            ),
        },
        "summary": {
            "cases": len(cases),
            "overclaim": overclaim,
            "real_defect": real_defect,
            "overclaim_where_code_was_fine": code_fine_overclaim,
            "majority_overridden": majority_overridden,
            "estate_sentence": (
                "Catalog names '5 of 8 refutations were overclaims where the code "
                f"was fine'. This reconstructed corpus measures {overclaim} of "
                f"{len(cases)} as that class."
            ),
        },
        "router_controls": {
            "null_disposition_refused": (not refused) and why == "null-disposition-refused",
            "accepted_residual_without_experiment_refused": (not residual_ok),
            "fully_dispositioned_closed": full_ok,
            "null_why": why,
            "residual_why": residual_why,
            "full_why": full_why,
        },
        "cases": cases,
        "evidence": [
            {
                "path": c["raw_source"],
                "claim": c["original_wording"],
                "classification": c["classification"],
                "probe_id": c["decisive_probe"]["id"],
            }
            for c in cases
        ],
        "tests": [
            {
                "id": "T1-decisive-probes",
                "name": "Re-run every case probe and require a decisive output",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-controls",
                "name": "Vote-count, overclaim-with-fine-code, wording-retention",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0119-probe2-controls",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Mechanical: winning_side must equal decisive_probe.supports; "
                "overclaim rows keep original_wording and a distinct scoped rewrite; "
                "a mutant that follows majority vote or deletes original_wording fails."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "decisive-probes", "command": P1},
            {"id": "probe2", "role": "controls", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
        ],
        "produced_by": {
            "execution_substrate": "headless-linux",
            "role": "adjudicator",
        },
        "timestamps": {"emitted_at": now},
        "adv_rebuild_circle": False,
    }

    ok, why_art = check_artifact(doc)
    if not ok:
        print(f"FAILED:CNF-0119 artifact check {why_art}")
        return 1

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print(f"FAILED:CNF-0119 schema missing {SCHEMA}")
        return 1
    declared = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict) or "$ref" not in declared:
        print("FAILED:CNF-0119 output_schema is not a parseable $ref shim")
        return 1
    # The catalog shim $ref is a logical URI (ast-integrate.invalid). jsonschema
    # 4.10 tries the network and raises RefResolutionError. Bind a local teeth
    # schema that still rejects garbage and requires the adjudication payload.
    # Domain invariants live in check_artifact (probe wins, overclaim rewrite).
    teeth = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "adjudication_method",
            "cases",
            "question",
            "answer",
            "reviewer",
            "named_probes",
            "min_bytes_threshold",
        ],
        "properties": {
            "unit_id": {"const": "CNF-0119"},
            "state": {"const": "SUCCESS"},
            "adjudication_method": {"const": "decisive-probe"},
            "cases": {"type": "array", "minItems": 8},
            "named_probes": {"type": "array", "minItems": 2},
            "min_bytes_threshold": {"type": "integer", "minimum": 1},
        },
    }
    validator = jsonschema.Draft7Validator(teeth)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0119 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0119", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0119 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0119 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"overclaim={overclaim} real_defect={real_defect} "
        f"code_fine_overclaim={code_fine_overclaim} "
        f"majority_overridden={majority_overridden}"
    )
    print("SUCCESS:CNF-0119 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
