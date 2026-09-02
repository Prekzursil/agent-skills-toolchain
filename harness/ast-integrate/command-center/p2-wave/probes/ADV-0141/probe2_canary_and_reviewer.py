#!/usr/bin/env python3
"""Probe 2: end-to-end canary in DIFFERENCE + independent COVERED re-derivation.

The reviewer route is sys.addaudithook('open'), mechanically different from the
injected opener log. Disagreement means one instrumentation is lying.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402
from gates import CANARY  # noqa: E402

ART = L.REPO / L.OUT_REL


def fail(msg: str, payload: dict | None = None) -> int:
    if payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:ADV-0141-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if L.SENTINEL not in raw:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    m = L.measure(L.UNIVERSE)
    if not m["live_ok"]:
        return fail("liveness canary on covered/app.py was not found")
    if m["gap_hits"]:
        return fail("gate found the DIFFERENCE canary; gap not demonstrated", {"hits": m["gap_hits"]})
    if not m["sets_agree"]:
        return fail(
            "opener log and audit-hook COVERED disagree",
            {
                "only_opener": sorted(set(m["covered_paths"]) - set(m["audit_paths"])),
                "only_audit": sorted(set(m["audit_paths"]) - set(m["covered_paths"])),
            },
        )
    missing_disp = [d["id"] for d in m["difference"] if not d.get("disposition") or not d.get("reason")]
    if missing_disp:
        return fail("difference missing disposition", {"ids": missing_disp})
    if not any("inner.zip!hidden.txt" in d["path"] for d in m["difference"]):
        return fail("canary host is not in DIFFERENCE")
    if CANARY in raw and CANARY[4:] in raw:
        # Artifact may mention the class; the body past prefix must not appear.
        # The constant is in this probe's source, not the artifact, unless leaked.
        if CANARY in raw:
            return fail("artifact contains full canary body")

    rep = L.report_view(doc)
    art_diff = rep.get("DIFFERENCE") or []
    if not art_diff:
        return fail("artifact DIFFERENCE empty")
    if not all(isinstance(d.get("disposition"), str) and d.get("reason") for d in art_diff):
        return fail("artifact DIFFERENCE missing disposition")
    canary = rep.get("canary") or {}
    if canary.get("gate_found_in_difference") is not False:
        return fail("artifact canary.gate_found_in_difference is not false")
    if canary.get("liveness_on_covered_path") is not True:
        return fail("artifact canary liveness is not true")
    if canary.get("synthetic") is not True:
        return fail("canary not marked synthetic")
    if (doc.get("reviewer") or {}).get("independent") is not True:
        return fail("artifact reviewer is not independent")
    if (doc.get("reviewer") or {}).get("verdict") != "PASS":
        return fail("artifact reviewer verdict is not PASS")
    if rep.get("covered_sets_agree") is not True:
        return fail("artifact reviewer sets do not agree")
    if rep.get("every_difference_has_disposition") is not True:
        return fail("every_difference_has_disposition is not true")

    payload = {
        "probe": "probe2-canary-and-reviewer",
        "canary_id": m["canary_id"],
        "gate_found_in_difference": False,
        "liveness_on_covered_path": True,
        "covered_sets_agree": True,
        "difference_count": len(m["difference"]),
        "pass": True,
        "unit_id": L.UNIT,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:ADV-0141-probe2 canary gap demonstrated; COVERED sets agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
