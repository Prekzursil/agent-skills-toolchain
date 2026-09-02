#!/usr/bin/env python3
"""Probe 1: regex set-intersection plus planted-collision detector control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import emit_artifact as E  # noqa: E402
import lib as L  # noqa: E402

ART = REPO / E.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0003-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.SENTINEL not in text:
        print("FAILED:WFA-0003-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0003-probe1 self-declared", doc.get("state"))
        return 1
    if doc.get("unit_id") != "WFA-0003":
        print("FAILED:WFA-0003-probe1 unit_id")
        return 1

    schema = json.loads((REPO / E.SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        errs = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
        if errs:
            print("FAILED:WFA-0003-probe1 schema", errs[0].message)
            return 1

    estate = C.materialize()
    paths = C.five_artifact_paths(estate)
    live_a = L.run_signal_a(paths)
    art_a = doc.get("signal_a") or {}
    if live_a["intersecting_count"] != art_a.get("intersecting_count"):
        print(
            "FAILED:WFA-0003-probe1 intersection count drift",
            live_a["intersecting_count"],
            art_a.get("intersecting_count"),
        )
        return 1
    if live_a["intersecting_tokens"] != art_a.get("intersecting_tokens"):
        print("FAILED:WFA-0003-probe1 intersecting token set drift")
        return 1

    planted = L.planted_detector_control(estate)
    print(
        f"planted token={planted['planted_token']} reported={planted['intersection_reported']} "
        f"kind={planted['kind']} pass={planted['pass']}"
    )
    if not planted["pass"]:
        print("FAILED:WFA-0003-probe1 planted collision not reported as SEMANTIC-CLASH")
        return 1
    if L.PLANT_TOKEN in live_a["intersecting_tokens"]:
        print("FAILED:WFA-0003-probe1 plant leaked into the production intersection")
        return 1

    pop = doc.get("population") or {}
    if pop.get("upstream_284_row_registry_present") is True:
        print("FAILED:WFA-0003-probe1 overclaim: 284-row registry is not on this worktree")
        return 1
    if pop.get("catalog_claimed_candidates") != 284:
        print("FAILED:WFA-0003-probe1 catalog claimed count missing")
        return 1
    if "does not claim a 284-row census" not in str(pop.get("note") or ""):
        print("FAILED:WFA-0003-probe1 missing 284-row non-claim note")
        return 1

    live_rows = C.live_presence(REPO)
    if any(r["present"] and r["path"].endswith("08-WORKFLOW-CANDIDATE-REGISTRY.json") for r in live_rows):
        print("note: live 08 registry unexpectedly present")
    elif any(r["present"] for r in live_rows if "08-WORKFLOW" in r["path"]):
        print("FAILED:WFA-0003-probe1 live 08 presence mismatch")
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-intersection",
                "intersecting_count": live_a["intersecting_count"],
                "planted_pass": planted["pass"],
                "unit_id": "WFA-0003",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0003-probe1 regex intersection plus planted collision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
