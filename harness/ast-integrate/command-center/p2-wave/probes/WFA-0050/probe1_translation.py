#!/usr/bin/env python3
"""Probe 1: translation completeness, roles, live-loop NON-TRANSFERABLE, no import.

Recomputes translations from fixtures. Does not trust the artifact's copied
construct table as the only signal; it re-runs adapter.py and diffs status.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import (  # noqa: E402
    imported_forbidden,
    live_loop_must_be_non_transferable,
    translate_crew,
    translate_groupchat,
)

UNIT = "WFA-0050"
ART = REPO / "command-center/wfa/WFA-0050-adapter-crew-autogen.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def _anchors(doc: dict) -> list[str]:
    missing = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if obj.get("kind") in {"role", "stage", "turn_policy", "stopping", "edge", "gate"}:
                if not obj.get("source_anchor"):
                    missing.append(str(obj.get("id")))
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(doc)
    return missing


def main() -> int:
    if imported_forbidden():
        return fail(f"forbidden modules already imported {imported_forbidden()}")
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0050" not in text:
        return fail("sentinel-absent")

    crew = translate_crew()
    group = translate_groupchat()
    if imported_forbidden():
        return fail(f"adapter imported {imported_forbidden()}")
    live_bad = live_loop_must_be_non_transferable()
    if live_bad:
        return fail(f"live-loop mapped {live_bad}")

    live_status = {
        c["id"]: c["status"]
        for c in crew["constructs"] + group["constructs"]
    }
    art_status = {c["id"]: c["status"] for c in doc.get("constructs") or []}
    if live_status != art_status:
        return fail(f"construct-status drift {live_status} vs {art_status}")

    for c in crew["constructs"] + group["constructs"]:
        if c["status"] not in {"MAPPED", "NON-TRANSFERABLE"}:
            return fail(f"construct {c['id']} status {c['status']}")
        if c.get("live_conversational_loop") and c["status"] != "NON-TRANSFERABLE":
            return fail(f"silent approximation {c['id']}")

    crew_maps = [n["payload"]["mapping"] for n in crew["ir"]["roles"]]
    ag_maps = [n["payload"]["mapping"] for n in group["ir"]["roles"]]
    if not any(m["council_id"] == "reviewer" for m in crew_maps):
        return fail("reviewer not mapped from crew")
    if not any(m.get("extension_id") == "crew-job-title" for m in crew_maps):
        return fail("crew job titles not extended")
    if not any(m["council_id"] == "critic" for m in ag_maps):
        return fail("critic not mapped")
    if not any(m["council_id"] == "chair" for m in ag_maps):
        return fail("manager not mapped to chair")
    if not any(m.get("extension_id") == "user-proxy-never" for m in ag_maps):
        return fail("NEVER user proxy force-fitted as author")
    if any(m["status"] not in {"MAPPED", "EXTEND"} for m in crew_maps + ag_maps):
        return fail("role neither mapped nor extended")

    missing = _anchors(crew["ir"]) + _anchors(group["ir"])
    if missing:
        return fail(f"ir nodes without source_anchor {missing}")
    if crew["ir"].get("execution_semantics") is not False:
        return fail("IR claimed execution semantics")

    if doc.get("worked_examples", {}).get("crew_id") != crew["native"]["id"]:
        return fail("artifact crew id mismatch")
    if doc.get("worked_examples", {}).get("groupchat_id") != group["native"]["id"]:
        return fail("artifact groupchat id mismatch")

    summary = {
        "crew_roles": [m["status"] for m in crew_maps],
        "ag_roles": [m["status"] for m in ag_maps],
        "mapped": sum(1 for s in live_status.values() if s == "MAPPED"),
        "non_transferable": sum(1 for s in live_status.values() if s == "NON-TRANSFERABLE"),
        "imported": imported_forbidden(),
        "live_loop_bad": live_bad,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:WFA-0050-probe1 translation mapped/NON-TRANSFERABLE "
        f"mapped={summary['mapped']} nt={summary['non_transferable']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
