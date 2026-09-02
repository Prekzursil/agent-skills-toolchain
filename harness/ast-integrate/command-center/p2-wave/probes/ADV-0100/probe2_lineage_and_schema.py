#!/usr/bin/env python3
"""Probe 2: transitive lineage COI, schema discrimination, overclaim gates.

Mechanically different from probe 1: walk incorporation edges instead of
matching the immediate author field. Author-field must stay SILENT on the
planted transitive fixture while lineage FIRES. Schema must reject garbage
and adjective false-positive rates. Production present-flags must match disk.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coi_filter as C  # noqa: E402
import fixtures as F  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"
SCHEMA = REPO / "command-center/schema/council-pathology-sim.schema.json"
PROD_COI = REPO / "tools/council/integrity/coi.py"


def _fail(msg: str) -> int:
    print(f"FAILED:ADV-0100-probe2 {msg}")
    return 1


def _resolve(rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = REPO / rel
    if not path.is_file():
        return False, f"missing {rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"{rel}:{line} out of range"
    if snippet not in lines[line - 1]:
        return False, f"{rel}:{line} snippet mismatch"
    return True, f"{rel}:{line}"


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        return _fail("jsonschema not installed")

    F.dump_json()
    trans = F.planted_transitive()
    field = C.analyse(trans, mode="author-field")
    lin = C.analyse(trans, mode="lineage")
    prod = C.analyse(trans, mode="production")
    print(C.status_line(field))
    print(C.status_line(lin))
    print(C.status_line(prod))

    if C.KNOWN_LINEAGE_AUTHOR not in field["eligible"]:
        return _fail("lineage author is not reviewer-eligible; fixture is wrong")
    if C.KNOWN_LINEAGE_AUTHOR in field["excluded"]:
        return _fail("author-field excluded lineage author; probes are not independent")
    if field["status"] != "SILENT":
        return _fail(f"author-field on transitive should be SILENT, got {field['status']}")
    print("author_field_misses_transitive=True")

    if lin["status"] != "FIRE" or C.KNOWN_LINEAGE_AUTHOR not in lin["excluded"]:
        return _fail("lineage walk did not exclude KNOWN-LINEAGE-AUTHOR")
    if not lin["independent_kept"]:
        return _fail("lineage walk over-broad: independent excluded")
    print("lineage_fires_on_transitive=True")

    # Immediate author carol is a synthesizer, not a counting reviewer, so
    # author-field silence is specifically the hidden original writer.
    if "CAROL-THIRD" in field["eligible"] and "CAROL-THIRD" not in field["excluded"]:
        return _fail("carol is reviewer-eligible yet author-field missed her")

    clean = C.analyse(F.clean_independent(), mode="lineage")
    if clean["status"] != "SILENT" or not clean["independent_kept"]:
        return _fail("lineage not silent on clean independent panel")
    print("lineage_silent_on_clean=True")

    if not ART.is_file():
        return _fail("artifact missing")
    if not SCHEMA.is_file():
        return _fail("schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

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
    except jsonschema.ValidationError as exc:
        return _fail(f"artifact fails schema: {exc.message}")
    print("schema_accepts_artifact=True")

    mutant = copy.deepcopy(doc)
    mutant["false_positive_rate"] = "low"
    adjective_rejected = False
    try:
        jsonschema.validate(mutant, schema)
    except jsonschema.ValidationError:
        adjective_rejected = True
    print(f"adjective_fp_rate_rejected={adjective_rejected}")
    if not adjective_rejected:
        return _fail("schema accepted adjective false-positive rate")

    live_coi = PROD_COI.is_file()
    claimed = (doc.get("production_census") or {}).get("integrity_coi_present")
    print(f"production_coi_present={live_coi} claimed={claimed}")
    if claimed is True and not live_coi:
        return _fail("overclaim: integrity/coi.py marked present")
    if claimed is not live_coi:
        return _fail("production_census.integrity_coi_present stale vs disk")

    leaked = list(prod.get("leaked_self_review") or [])
    want = "CONFIRMED" if leaked else "REFUTED"
    targets = {t.get("id"): t.get("verdict") for t in (doc.get("targets") or [])}
    got = targets.get("T-TRANSITIVE-LINEAGE-SELF-REVIEW")
    print(f"artifact_transitive_verdict={got} want={want} leaked={leaked}")
    if got != want:
        return _fail(f"artifact T-TRANSITIVE-LINEAGE-SELF-REVIEW {got} != live {want}")

    for t in doc.get("targets") or []:
        if t.get("verdict") not in {
            "CONFIRMED",
            "REFUTED",
            "PARTIAL",
            "NOT-CHECKED",
            "BLOCKED",
        }:
            return _fail(f"illegal target verdict {t}")

    rev = R.review()
    print(
        f"reviewer_live_verdict={rev['verdict']} independent={rev['independent']} "
        f"artifact_ok={rev['artifact_ok']}"
    )
    if rev["verdict"] != "PASS":
        return _fail(f"reviewer {rev['verdict']} {rev.get('artifact_note')}")
    if doc.get("reviewer", {}).get("independent") is not True:
        return _fail("artifact reviewer.independent is not true")
    if doc.get("reviewer", {}).get("vendor_constraint_met") is True:
        return _fail("cannot claim openai/gpt-5-codex signed this")
    added = (doc.get("reviewer") or {}).get("added_failure_mode") or {}
    if added.get("id") != "FM-PSEUDONYM-ALIAS":
        return _fail("reviewer did not add FM-PSEUDONYM-ALIAS")

    anchors = doc.get("evidence") or []
    if len(anchors) < 2:
        return _fail("need >=2 evidence anchors")
    for i, ev in enumerate(anchors):
        path = ev.get("path")
        line = ev.get("line")
        snippet = ev.get("snippet")
        if not path or not isinstance(line, int) or not snippet:
            continue
        ok, note = _resolve(path, line, snippet)
        print(f"anchor[{i}] ok={ok} {note}")
        if not ok:
            return _fail(note)

    print("SUCCESS:ADV-0100-probe2 lineage schema overclaim reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
