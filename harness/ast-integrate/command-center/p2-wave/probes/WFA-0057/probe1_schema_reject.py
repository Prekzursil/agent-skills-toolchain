#!/usr/bin/env python3
"""Probe 1: schema-level rejection of missing and empty-string anchors on every IR node kind.

Evidence A: attempting to construct an anchorless node is rejected by the schema.
Empty-string is rejected as firmly as missing (both hard-reject; both schema-invalid).
Licence class is required the same way.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ir import NODE_KINDS, classify_node, schema_errors  # noqa: E402
from pipeline import schema_assertion  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0057-ir-provenance-carry.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0057-probe1 {msg}")
    return 1


def main() -> int:
    assertion = schema_assertion()
    n = len(NODE_KINDS)
    if assertion["missing_anchor_rejected"] != n:
        return fail(f"missing-anchor not rejected on all kinds {assertion['missing_anchor_rejected']}/{n}")
    if assertion["empty_anchor_rejected"] != n:
        return fail(f"empty-anchor not rejected on all kinds {assertion['empty_anchor_rejected']}/{n}")
    if assertion["missing_licence_rejected"] != n:
        return fail("missing-licence not rejected on all kinds")
    if assertion["empty_licence_rejected"] != n:
        return fail("empty-licence not rejected on all kinds")
    if assertion["valid_accepted"] != n:
        return fail(f"valid nodes not accepted {assertion['valid_accepted']}/{n}")
    if not assertion["empty_string_rejected_as_firmly_as_missing"]:
        return fail("empty-string not as firm as missing")

    for row in assertion["per_kind"]:
        kind = row["kind"]
        if not row["missing_anchor_schema"] or not row["empty_anchor_schema"]:
            return fail(f"{kind} schema did not reject missing or empty anchor")
        if "anchor-missing" not in row["missing_anchor_runtime"]:
            return fail(f"{kind} runtime missed missing-anchor")
        if "anchor-empty" not in row["empty_anchor_runtime"]:
            return fail(f"{kind} runtime missed empty-anchor")
        if "anchor-empty" not in row["whitespace_anchor_runtime"]:
            return fail(f"{kind} whitespace anchor not treated as empty")
        # Equal firmness: both are hard rejects (non-empty code lists), not warnings.
        if not row["missing_anchor_runtime"] or not row["empty_anchor_runtime"]:
            return fail(f"{kind} unequal firmness missing vs empty")

    # Direct schema construction (not via make_node, which refuses before schema).
    sample = {"kind": "Stage", "id": "s1", "licence_class": "mit"}
    if not schema_errors(sample) or "anchor-missing" not in classify_node(sample):
        return fail("direct missing-anchor construction was accepted")
    empty = {"kind": "Stage", "id": "s1", "anchor": "", "licence_class": "mit"}
    if not schema_errors(empty) or "anchor-empty" not in classify_node(empty):
        return fail("direct empty-anchor construction was accepted")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0057" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sa = doc.get("schema_assertion") or {}
    if sa.get("missing_anchor_rejected") != n or sa.get("empty_anchor_rejected") != n:
        return fail("artifact schema_assertion does not match live count")
    if sa.get("empty_string_rejected_as_firmly_as_missing") is not True:
        return fail("artifact does not record empty-string firmness")

    payload = {
        "probe": "probe1-schema-reject",
        "unit_id": "WFA-0057",
        "computed_not_asserted": True,
        "kinds": n,
        "missing_anchor_rejected": assertion["missing_anchor_rejected"],
        "empty_anchor_rejected": assertion["empty_anchor_rejected"],
        "empty_as_firm_as_missing": True,
        "whitespace_treated_as_empty": True,
        "valid_accepted": assertion["valid_accepted"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"kinds={n} missing_anchor_rejected={n} empty_anchor_rejected={n} "
        "empty_as_firm_as_missing=True schema_ok=True"
    )
    print("SUCCESS:WFA-0057-probe1 schema-reject missing-and-empty-anchor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
