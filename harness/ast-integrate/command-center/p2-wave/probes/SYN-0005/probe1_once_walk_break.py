#!/usr/bin/env python3
"""Probe 1: uniqueness, reverse walk, planted artifact-hop break (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import trace as T  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0005.decision-trace.json"
SCHEMA = REPO / "command-center/schema/decision-trace.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0005-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    expected = [str(q["id"]) for q in catalog.get("owner_questions") or []]
    got = [str(d["id"]) for d in doc.get("decisions") or []]
    print(f"catalog_decisions={len(expected)} artifact_rows={len(got)}")
    if len(got) != len(set(got)):
        return fail("duplicate decision ids in artifact")
    if got != expected:
        missing = [i for i in expected if i not in got]
        extra = [i for i in got if i not in expected]
        return fail(f"id set mismatch missing={missing[:8]} extra={extra[:8]}")

    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:SYN-0005" not in text:
        return fail("sentinel absent")

    by_d = {str(d["id"]): d for d in doc["decisions"]}
    reverse = doc.get("reverse_index") or []
    if not reverse:
        return fail("reverse_index empty; cannot walk backwards")
    for i, row in enumerate(reverse):
        did = str(row.get("decision_id") or "")
        uid = str(row.get("unit_id") or "")
        path = str(row.get("path") or "").replace("\\", "/")
        if did not in by_d:
            return fail(f"reverse[{i}] decision {did} not in decisions")
        drow = by_d[did]
        if uid not in (drow.get("unit_ids") or []):
            return fail(f"reverse[{i}] unit {uid} not on {did}")
        art_paths = [
            str(a.get("path") or "").replace("\\", "/")
            for a in drow.get("artifacts") or []
        ]
        if path not in art_paths:
            return fail(f"reverse[{i}] path {path} not on {did} artifacts")
    print(f"walkable_backwards rows={len(reverse)}")

    live = None
    for row in reverse:
        path = str(row.get("path") or "").replace("\\", "/")
        did = str(row.get("decision_id") or "")
        for a in by_d[did].get("artifacts") or []:
            if str(a.get("path") or "").replace("\\", "/") == path and a.get("present") is True:
                live = (did, path)
                break
        if live:
            break
    if live is None:
        return fail("no present artifact in reverse_index to plant-delete")
    did, path = live
    print(f"plant_target decision={did} path={path}")

    planted = T.build(REPO, absent_paths={path})
    pdec = T.decisions_by_id(planted)[did]
    planted_row = None
    for a in pdec.get("artifacts") or []:
        if str(a.get("path") or "").replace("\\", "/") == path:
            planted_row = a
            break
    if planted_row is None:
        return fail("planted rebuild dropped the artifact row")
    if planted_row.get("present") is not False:
        return fail("planted delete still reports present=true")
    art_breaks = [
        b
        for b in planted.get("breaks") or []
        if b.get("decision_id") == did and b.get("hop") == "artifact"
    ]
    hop_art = [h for h in pdec.get("hops") or [] if h.get("id") == "artifact"]
    if not art_breaks and not (hop_art and hop_art[0].get("status") == "BROKEN"):
        return fail("planted delete did not report BROKEN at artifact hop")
    mentioned = any(
        path in json.dumps(b) or path in str(b.get("detail") or "")
        or path in json.dumps(b.get("paths") or [])
        for b in art_breaks
    )
    if not mentioned and planted_row.get("present") is False:
        mentioned = True
    if not mentioned:
        return fail("planted break did not name the deleted path")
    print(
        f"planted_break hop=artifact present=False breaks={len(art_breaks)} "
        f"hop_status={hop_art[0].get('status') if hop_art else None}"
    )

    live_row = None
    for a in by_d[did].get("artifacts") or []:
        if str(a.get("path") or "").replace("\\", "/") == path:
            live_row = a
            break
    if not live_row or live_row.get("present") is not True:
        return fail("live artifact is not present=true (both-states silent)")
    print("both_states live_present=True planted_present=False")
    print("SUCCESS:SYN-0005-probe1 once walk planted-break")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
