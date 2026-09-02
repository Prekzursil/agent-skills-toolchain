#!/usr/bin/env python3
"""Probe 2: partition covers the union; every candidate parsed against schema.

Re-validates the live artifact. Recomputes coverage from partition.py.
Does not rewrite the catalog artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import partition as P  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0008.candidate-syntheses.json"
SCHEMA = REPO / "command-center/schema/synthesis-candidate.schema.json"
UNIT = "SYN-0008"
COMPLETION = (
    "SUCCESS:SYN-0008 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and >=3 candidates exist, "
    "span >=2 vendors, and the leak fixture is recorded as DENIED. Any other "
    "terminal state is FAILED:SYN-0008 <classification> with the diagnostic "
    "tail attached."
)
GARBAGE = [
    {},
    {"unit_id": "SYN-0008", "state": "SUCCESS"},
    {"candidates": [], "sentinel": "SUCCESS:SYN-0008"},
]


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    if not SCHEMA.is_file():
        return fail("schema missing")
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    schema.pop("$id", None)
    jsonschema.Draft7Validator.check_schema(schema)
    root_v = jsonschema.Draft7Validator(schema)
    errs = list(root_v.iter_errors(doc))
    if errs:
        return fail(f"artifact schema {errs[0].message}")

    for garbage in GARBAGE:
        g_errs = list(root_v.iter_errors(garbage))
        if not g_errs:
            return fail(f"schema accepted garbage {garbage}")

    if COMPLETION not in raw:
        return fail("completion sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    candidates = doc.get("candidates") or []
    if len(candidates) < 3:
        return fail(f"candidate_count {len(candidates)}")
    vendors = {str(c.get("vendor") or "") for c in candidates}
    vendors.discard("")
    if len(vendors) < 2:
        return fail(f"vendor span {sorted(vendors)}")

    resolver = jsonschema.RefResolver.from_schema(schema)
    cand_v = jsonschema.Draft7Validator(
        schema["definitions"]["candidate"], resolver=resolver
    )
    manifests = []
    for cand in candidates:
        c_errs = list(cand_v.iter_errors(cand))
        if c_errs:
            return fail(f"candidate {cand.get('id')} schema {c_errs[0].message}")
        if not cand.get("parsed"):
            return fail(f"candidate {cand.get('id')} parsed=False")
        if cand.get("exit_code") != 0:
            return fail(f"candidate {cand.get('id')} exit {cand.get('exit_code')}")
        if cand.get("counts_as_result") is not True:
            return fail(f"candidate {cand.get('id')} not counted")
        if cand.get("classification") != "completed":
            return fail(f"candidate {cand.get('id')} class {cand.get('classification')}")
        if int(cand.get("output_bytes") or 0) <= 0:
            return fail(f"candidate {cand.get('id')} empty output")
        if cand.get("prompt_transport") != "file":
            return fail(f"candidate {cand.get('id')} prompt not by file")
        if cand.get("foreground") is not True:
            return fail(f"candidate {cand.get('id')} not foreground")
        man = cand.get("partition_manifest") or {}
        manifests.append(man)

    cov = P.coverage(manifests)
    if cov["zero_agent_classes"]:
        return fail(f"zero-agent classes {cov['zero_agent_classes']}")
    for cls in P.EVIDENCE_FILES:
        if not cov["agents_per_class"].get(cls):
            return fail(f"class {cls} reached zero agents")

    art_cov = doc.get("partition_coverage") or {}
    if art_cov.get("zero_agent_classes"):
        return fail(f"artifact zero-agent {art_cov.get('zero_agent_classes')}")

    reviewer = doc.get("reviewer") or {}
    intersection = reviewer.get("intersection")
    if intersection != []:
        return fail(f"reviewer/author intersection {intersection}")
    authors = set(reviewer.get("author_roster") or [])
    rid = str(reviewer.get("reviewer_id") or "")
    if rid in authors:
        return fail("reviewer authored a candidate")
    if reviewer.get("verdict") != "PASS":
        return fail(f"reviewer verdict {reviewer.get('verdict')}")

    parse_rows = doc.get("schema_parsed_before_fan_in") or []
    if len(parse_rows) < 3:
        return fail("schema-before-fan-in rows missing")
    if not all(r.get("schema_ok") for r in parse_rows):
        return fail("schema-before-fan-in reported failure")

    print(
        json.dumps(
            {
                "probe": "probe2-partition-and-schema",
                "unit_id": UNIT,
                "candidates": len(candidates),
                "vendors": sorted(vendors),
                "zero_agent_classes": cov["zero_agent_classes"],
                "garbage_rejected": True,
                "reviewer_intersection": intersection,
                "schema_before_fan_in": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"candidates={len(candidates)} vendors={sorted(vendors)} "
        f"zero_agent={cov['zero_agent_classes']} schema=PASS"
    )
    print("SUCCESS:SYN-0008-probe2 partition union and schema-before-fan-in")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
