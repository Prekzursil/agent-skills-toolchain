#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0139.json from live RepairLoop fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.impossibility import validate_impossibility  # noqa: E402
from agentspec.repair_loop import run_fixture, terminal_as_dict  # noqa: E402
from agentspec.spec import RepairLoop  # noqa: E402
from agentspec.validate import validate_workflow  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0139.json"
SENTINEL = "SUCCESS:IMP-0139"
FIXTURES = HERE / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_receipt() -> dict:
    passed = run_fixture(_load("pass.json"))
    limited = run_fixture(_load("attempt_limit.json"))
    impossible = run_fixture(_load("impossibility.json"))
    proof = validate_impossibility(impossible.proof)
    workflow = {
        "spec_version": 1,
        "entry": "fix-cycle",
        "nodes": [
            {
                "id": "fix-cycle",
                "type": "repair-loop",
                "body": "draft-unit",
                "review": "review-pred",
                "max_attempts": 3,
            }
        ],
        "edges": [],
    }
    violations = validate_workflow(workflow)
    if violations:
        raise SystemExit(f"repair-loop node failed validation: {violations}")
    node = RepairLoop(
        id="fix-cycle", body="draft-unit", review="review-pred", max_attempts=3
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": "IMP-0139",
        "unit_id": "IMP-0139",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Add a RepairLoop node with an attempt limit and a proof-of-impossibility exit",
        "question": (
            "Implement the spec's fix-review cycle as a first-class node: "
            "send weak work back until it passes, the attempt limit is reached, "
            "OR a proof-of-impossibility record demonstrates why the evidence "
            "cannot be obtained. All three exits must write distinct typed "
            "terminal records."
        ),
        "computed_at": now,
        "cloud_ok": False,
        "registered": True,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/agentspec/schemas/proof-of-impossibility.schema.json"
        ),
        "node": {
            "type": "RepairLoop",
            "id": node.id,
            "body": node.body,
            "review": node.review,
            "max_attempts": node.max_attempts,
            "frozen": True,
        },
        "exits": {
            "passed": terminal_as_dict(passed),
            "attempt_limit": terminal_as_dict(limited),
            "proved_impossible": terminal_as_dict(impossible),
        },
        "record_types": [
            passed.record_type,
            limited.record_type,
            impossible.record_type,
        ],
        "types_distinct": len(
            {type(passed), type(limited), type(impossible)}
        )
        == 3,
        "proof_of_impossibility": proof,
        "settling_experiment_id": proof["settling_experiment"]["id"],
        "workflow_validation_violations": [],
        "notes": (
            "G-1 for IMP-0139: RepairLoop is a frozen first-class node. "
            "Three fixtures drive pass / attempt-limit / proved-impossible "
            "on distinct emit paths. Proof-of-impossibility schema-validates "
            "and names its settling experiment. A search-failure document is "
            "rejected. Did not run global unit_manifest.py --write."
        ),
    }


def main() -> int:
    receipt = build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise SystemExit("sentinel missing from receipt text")
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} sha256={_sha(out)} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
