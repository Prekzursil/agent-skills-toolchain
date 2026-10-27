#!/usr/bin/env python3
"""IMP-0096 probe2: negative controls.
(a) a record missing a required reproducibility field is REJECTED;
(b) the schema validator rejects a record missing required properties;
(c) a schema-valid record whose reproduction command cannot re-run is NOT
    evidence (evaluate_evidence -> is_evidence False).
Good-state twin: the probe1 attachment reproduces (both-states)."""
from __future__ import annotations

import glob
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA = REPO / "tools" / "marketplace" / "schema" / "benchmark-evidence.schema.json"
ATTACH = REPO / "tools" / "marketplace" / "attachments" / "fixture.bench.demo-imp-0096.live.primary.json"


def load_be():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "benchmark_evidence.py")))
    spec = importlib.util.spec_from_file_location("imp0096_be2", hits[0])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_against_schema(rec: dict, schema: dict) -> list:
    errs = []
    for req in schema.get("required", []):
        if req not in rec:
            errs.append(f"missing:{req}")
    return errs


def main() -> int:
    be = load_be()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    # good twin: the live attachment (written by probe1)
    good = json.loads(ATTACH.read_text(encoding="utf-8")) if ATTACH.is_file() else None
    good_evidence = bool(good) and be.evaluate_evidence(dict(good), repo=REPO).get("is_evidence") is True

    # (a) missing required field -> rejected
    hole = dict(good or {})
    hole["environment_fingerprint"] = ""
    try:
        be.validate_record(hole)
        missing_rejected = False
    except be.EvidenceError:
        missing_rejected = True

    # (b) schema rejects missing required property
    hole2 = dict(good or {})
    hole2.pop("commit_sha", None)
    schema_rejects = validate_against_schema(hole2, schema) != []

    # (c) schema-valid but unrerunnable is not evidence
    dead = dict(good or {})
    dead["reproduction_command"] = f'{sys.executable} -c "import sys; sys.exit(3)"'
    ev = be.evaluate_evidence(dict(dead), repo=REPO)
    dead_status = ev["reproduction"]["status"]
    dead_not_evidence = ev.get("is_evidence") is False and dead_status == "UNREPRODUCED"

    result = {
        "unit_id": "IMP-0096",
        "probe": "probe2-negative-controls",
        "missing_fingerprint_rejected": missing_rejected,
        "schema_rejects_hole": schema_rejects,
        "dead_command_status": dead_status,
        "unrerunnable_not_evidence": dead_not_evidence,
        "good_twin_reproduces": good_evidence,
        "pass": missing_rejected and schema_rejects and dead_not_evidence and good_evidence,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0096-probe2 negative controls fire; good twin reproduces (both-states)"
            if result["pass"] else
            "FAILED:IMP-0096-probe2 negative-control contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
