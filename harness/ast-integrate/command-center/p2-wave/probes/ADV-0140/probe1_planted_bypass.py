#!/usr/bin/env python3
"""Named probe 1: planted ungated publish is found and proven on FakeSink."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import enumerate as EN  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0140-owner-gate-bypass.json"
SENTINEL_PREFIX = "SUCCESS:ADV-0140 emitted only when"
CLASSES = (
    "public_publishing",
    "unbounded_or_paid_external_spend",
    "deleting_user_data",
    "changing_security_posture",
    "creating_public_repositories_or_organizations",
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0140-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL_PREFIX not in text:
        print("FAILED:ADV-0140-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "ADV-0140":
        print("FAILED:ADV-0140-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0140-probe1 self-declared", doc.get("state"))
        return 1
    ac = doc.get("action_classes") or {}
    if any(c not in ac or not isinstance(ac[c].get("paths"), list) for c in CLASSES):
        print("FAILED:ADV-0140-probe1 missing class path set")
        return 1

    enum = EN.enumerate_all()
    planted = enum["planted_bypass"]
    proof = enum["fake_sink_receipt"]
    ok = (
        bool(planted)
        and proof.get("substituted") is True
        and proof.get("real_transport_invoked") is False
        and bool(proof.get("calls"))
        and "pypi.org" in proof["calls"][0]["url"]
        and proof["calls"][0]["method"] == "POST"
        and doc.get("tests", {}).get("planted_bypass_found") is True
        and doc.get("no_real_sink_executed") is True
    )
    payload = {
        "probe": "probe1-planted-bypass-fake-sink",
        "unit_id": "ADV-0140",
        "pass": bool(ok),
        "planted_path_id": planted[0]["path_id"] if planted else None,
        "fake_calls": proof.get("calls"),
        "real_transport_invoked": proof.get("real_transport_invoked"),
        "classes": sorted(ac.keys()),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0140-probe1 planted bypass or fake-sink proof")
        return 1
    print("SUCCESS:ADV-0140-probe1 planted ungated publish found; FakeSink substituted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
