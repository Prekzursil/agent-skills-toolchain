#!/usr/bin/env python3
"""Probe 2: schema discriminates; dual-rail intersection; overclaim gates."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import captures_lib as C  # noqa: E402
import features as F  # noqa: E402
import intersect as I  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/research/RES-0031.json"
SCHEMA = REPO / "command-center/schema/compatibility-matrix.schema.json"
INTERSECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "required": ["computed", "members", "cardinality"],
    "properties": {
        "computed": {"type": "boolean"},
        "members": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "cardinality": {"type": "integer", "minimum": 0},
    },
}


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0031-probe2 {msg}")
    return 1


def _bind_intersection(schema: dict) -> dict:
    """Catalog schema allows extra keys; bind intersection so 'eyeballed' fails."""
    bound = copy.deepcopy(schema)
    props = dict(bound.get("properties") or {})
    props["intersection"] = INTERSECTION_SCHEMA
    bound["properties"] = props
    return bound


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        return _fail("jsonschema not installed")
    if not ART.is_file():
        return _fail("artifact missing")
    if not SCHEMA.is_file():
        return _fail("schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    bound = _bind_intersection(schema)
    garbage_rejected = 0
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.validate(g, schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
    print(f"schema_garbage_rejected={garbage_rejected}/3")
    if garbage_rejected != 3:
        return _fail("schema accepts garbage")
    try:
        jsonschema.validate(doc, schema)
        jsonschema.validate(doc, bound)
    except jsonschema.ValidationError as exc:
        return _fail(f"artifact fails schema: {exc.message}")
    print("schema_accepts_artifact=True")

    mutant = copy.deepcopy(doc)
    mutant["intersection"] = "eyeballed"
    adjective_rejected = False
    try:
        jsonschema.validate(mutant, bound)
    except jsonschema.ValidationError:
        adjective_rejected = True
    print(f"eyeballed_intersection_rejected={adjective_rejected}")
    if not adjective_rejected:
        return _fail("schema accepted non-object intersection")

    text = ART.read_text(encoding="utf-8")
    if F.CATALOG_SENTINEL not in text:
        return _fail("catalog completion_sentinel absent from artifact")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")

    extracted = F.extract(C.by_id(C.load_metas()))
    live_inter = I.intersection(extracted["e2_sets"])
    claimed = list((doc.get("intersection") or {}).get("members") or [])
    print(f"live_intersection={live_inter}")
    print(f"artifact_intersection={claimed}")
    if claimed != live_inter:
        return _fail("artifact intersection does not match live set operations")
    if (doc.get("intersection") or {}).get("computed") is not True:
        return _fail("intersection not marked computed")
    if int((doc.get("intersection") or {}).get("cardinality") or -1) != len(live_inter):
        return _fail("intersection.cardinality mismatch")

    for pid in live_inter:
        for vendor in F.VENDORS:
            hits = [
                c
                for c in (doc.get("cells") or [])
                if c.get("primitive_id") == pid and c.get("vendor") == vendor
            ]
            if not hits:
                return _fail(f"missing cell {pid}/{vendor}")
            cell = hits[0]
            if cell.get("evidence_tier") != "E2" or len(cell.get("rails") or []) < 2:
                return _fail(f"intersection cell {pid}/{vendor} is not dual-rail")
            for rail in cell["rails"]:
                if int(rail.get("http_status") or 0) != 200:
                    return _fail(f"rail http_status not 200 for {pid}/{vendor}")
                if not rail.get("sha256") or not rail.get("permalink") or not rail.get("fetched_at"):
                    return _fail(f"rail metadata incomplete for {pid}/{vendor}")

    overclaims = {"first-class-memories", "memory-bank-methodology", "custom-modes"}
    leaked = sorted(set(claimed) & overclaims)
    print(f"overclaim_leaks={leaked}")
    if leaked:
        return _fail(f"overclaim in intersection: {leaked}")

    rev = R.review(extracted, doc)
    print(f"reviewer_verdict={rev['verdict']}")
    if rev["verdict"] != "PASS":
        return _fail(f"reviewer {rev['verdict']}: {rev.get('findings')}")
    art_rev = doc.get("reviewer") or {}
    if art_rev.get("independent") is not True:
        return _fail("reviewer.independent is not true")
    if art_rev.get("verdict") != "PASS":
        return _fail("artifact reviewer verdict is not PASS")
    print("SUCCESS:RES-0031-probe2 schema dual-rail overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
