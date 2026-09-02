#!/usr/bin/env python3
"""Probe 2: calibration below the JSON number refuses arming.

The criterion is the JSON number in tools/router/shadow_config.json, not a
float scraped from arming_criterion_prose. A prose-parser mutant would arm
the below-criterion sample; production must refuse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from scenario import measure_arming_gate  # noqa: E402
from tools.router.shadow import (  # noqa: E402
    REFUSE_BELOW_CRITERION,
    REFUSE_OWNER_SIGNOFF,
    numeric_arming_criterion,
)

ART = REPO / "command-center" / "receipts" / "IMP-0406.json"
SENTINEL = "SENTINEL:IMP-0406:ROUTER-SHADOW-ZERO-EFFECT"
CONFIG = "tools/router/shadow_config.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0406-probe2 {msg}")
    return 1


def main() -> int:
    g = measure_arming_gate()
    print(json.dumps(g, sort_keys=True))
    live = numeric_arming_criterion()
    if live != g["arming_criterion"]:
        return fail("numeric_arming_criterion drifted from measure")
    if g["arming_criterion_type"] != "float":
        return fail(f"criterion type {g['arming_criterion_type']}")
    if g["below_armed"]:
        return fail("below-criterion calibration was armed")
    if g["below_reason"] != REFUSE_BELOW_CRITERION:
        return fail(f"below reason={g['below_reason']}")
    if not g["below_still_shadow"]:
        return fail("refused arm still mutated injected context")
    if not g["gate_uses_json_number"]:
        return fail("gate is not using the JSON number")
    if not g["prose_mutant_would_arm"]:
        return fail("prose-parser mutant did not arm (control inert)")
    if g["prose_extracted_criterion"] is None:
        return fail("prose trap has no number for the mutant to eat")
    if g["prose_extracted_criterion"] == g["arming_criterion"]:
        return fail("prose number collided with the real criterion")
    if not g["missing_criterion_refused"]:
        return fail("config without arming_criterion was accepted")
    if not g["bool_criterion_refused"]:
        return fail("boolean true was accepted as a criterion")
    if g["no_signoff_armed"]:
        return fail("arming succeeded without owner sign-off")
    if g["no_signoff_reason"] != REFUSE_OWNER_SIGNOFF:
        return fail(f"no-signoff reason={g['no_signoff_reason']}")

    cfg_doc = json.loads((REPO / CONFIG).read_text(encoding="utf-8"))
    raw = cfg_doc.get("arming_criterion")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return fail("committed config lost the JSON number")
    if float(raw) != live:
        return fail("committed config number drifted from loader")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    recorded = ((doc.get("report") or {}).get("arming_gate")) or doc.get("arming_gate") or {}
    if recorded.get("arming_criterion") != live:
        return fail("receipt criterion drift")
    if recorded.get("below_reason") != REFUSE_BELOW_CRITERION:
        return fail("receipt below_reason drift")
    if recorded.get("below_armed") is not False:
        return fail("receipt did not record below_armed=false")

    print(
        f"criterion={live} below_refused=True prose_mutant_would_arm=True "
        f"missing_refused=True bool_refused=True"
    )
    print("SUCCESS:IMP-0406-probe2 arming-gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
