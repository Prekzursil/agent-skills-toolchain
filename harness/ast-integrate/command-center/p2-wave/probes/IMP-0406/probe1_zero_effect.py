#!/usr/bin/env python3
"""Probe 1: shadow on vs shadow off leaves injected context byte-identical.

The selector MUST produce a non-empty would-be payload (otherwise zero-effect
is a tautology). A leaky mutant that concatenates that payload must diverge.
An independently armed copy must actually inject, proving the injector exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from scenario import measure_zero_effect  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0406.json"
SENTINEL = "SENTINEL:IMP-0406:ROUTER-SHADOW-ZERO-EFFECT"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0406-probe1 {msg}")
    return 1


def main() -> int:
    z = measure_zero_effect()
    print(json.dumps(z, sort_keys=True))
    if z["would_inject_bytes"] <= 0:
        return fail("would-be payload empty; zero-effect is tautological")
    if not z["byte_identical"]:
        return fail(
            "shadow-on and shadow-off injected_context differ "
            f"on={z['shadow_on_sha256']} off={z['shadow_off_sha256']}"
        )
    if z["shadow_injected"] or z["off_injected"]:
        return fail("shadow path injected into the session")
    if z["zero_delta_bytes"] != 0:
        return fail(f"delta_bytes={z['zero_delta_bytes']}")
    if z["shadow_on_sha256"] != z["baseline_sha256"]:
        return fail("shadow-on digest drifted from baseline")
    if z["shadow_off_sha256"] != z["baseline_sha256"]:
        return fail("shadow-off digest drifted from baseline")
    if not z["leak_differs"]:
        return fail("leaky mutant did not change injected bytes (control inert)")
    if z["leak_sha256"] == z["baseline_sha256"]:
        return fail("leaky mutant digest collided with baseline")
    if not z["armed_injected"] or not z["armed_differs"]:
        return fail("armed copy did not inject; shadow zero-effect would be a stub")
    if not z["armed_payload_appended"]:
        return fail("armed injection was not baseline+payload")
    if "cap.lint.ruff" not in z["selected_ids"]:
        return fail(f"selector missed lint capability: {z['selected_ids']}")
    if z["shadow_log_len"] < 1:
        return fail("shadow log empty; would-be injection was not recorded")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    recorded = ((doc.get("report") or {}).get("zero_effect")) or doc.get("zero_effect") or {}
    if recorded.get("shadow_on_sha256") != z["shadow_on_sha256"]:
        return fail("receipt shadow_on_sha256 drift")
    if recorded.get("would_inject_sha256") != z["would_inject_sha256"]:
        return fail("receipt would_inject_sha256 drift")
    if recorded.get("byte_identical") is not True:
        return fail("receipt did not record byte_identical")

    print(
        "byte_identical=True leak_differs=True armed_differs=True "
        f"would_bytes={z['would_inject_bytes']} delta={z['zero_delta_bytes']}"
    )
    print("SUCCESS:IMP-0406-probe1 zero-effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
