#!/usr/bin/env python3
"""Probe 1: YAML parse of CI workflows with resolved run commands.

Recomputes the ordered job/step table. The planted registry-only ghost
must be DEAD. Matrix fixture must expand to 6 legs. Does not trust the
artifact self-report without a live re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    GHOST,
    ORIGIN_EXPECTED,
    TRULY_ABSENT,
    assert_control,
    build,
    probe1_payload,
)

ART = REPO / "command-center/audit/AUD-0041-ci-step-inventory.json"
SENTINEL = "SUCCESS:AUD-0041"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0041-probe1 {msg}")
    return 1


def main() -> int:
    cen = build()
    payload = probe1_payload(cen)
    print(json.dumps(payload, sort_keys=True))
    assert_control(cen)
    if payload["origin_totals"] != ORIGIN_EXPECTED:
        return fail(f"origin totals {payload['origin_totals']}")
    if payload["ghost"] != "DEAD":
        return fail("ghost not DEAD on YAML parse")
    if payload["truly_absent"] != "DEAD":
        return fail("truly_absent not DEAD")
    if payload["mention_only"] != "DEAD":
        return fail("comment mention counted as a workflow")
    if payload["matrix_leg_count"] != 6:
        return fail(f"matrix legs {payload['matrix_leg_count']} want 6")
    if payload["plain_leg_count"] != 1:
        return fail(f"plain legs {payload['plain_leg_count']} want 1")
    if not payload["on_key_boolean_trap_survived"]:
        return fail("on:-as-True trap swallowed triggers")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    art_ctl = doc.get("planted_control") or {}
    if art_ctl.get("probe1_verdict") != "DEAD":
        return fail("artifact probe1_verdict not DEAD")
    if art_ctl.get("independent") is not True:
        return fail("artifact control not independent")
    by_id = {i["id"]: i for i in doc.get("items") or [] if i.get("kind") == "module"}
    row = by_id.get(GHOST)
    if not row or row.get("probe1_verdict") != "DEAD":
        return fail("artifact ghost item probe1 not DEAD")
    art_origin = doc.get("origin_totals") or {}
    for key, want in ORIGIN_EXPECTED.items():
        if art_origin.get(key) != want:
            return fail(f"artifact origin {key}={art_origin.get(key)} want={want}")
    if art_origin.get("steps") != payload["origin_totals"]["steps"]:
        return fail("artifact origin step count drifted from live YAML parse")
    print(
        f"yaml_parse origin_files={payload['origin_totals']['workflow_files']} "
        f"jobs={payload['origin_totals']['jobs']} "
        f"steps={payload['origin_totals']['steps']} "
        f"matrix_legs=6 ghost=DEAD"
    )
    print("SUCCESS:AUD-0041-probe1 live YAML parse matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
