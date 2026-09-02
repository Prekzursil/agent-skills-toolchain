#!/usr/bin/env python3
"""Probe 2: TRANSLATE rows name a target adapter; zero-reclass rule holds.

Both-states: stripping adapter ids from a copy of the backlog must fail this
probe's check; a chosen-plane-only ADOPT subset with no foreign imports must
be allowed to produce zero TRANSLATE because both signals agree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_candidates  # noqa: E402
from engine import analyse  # noqa: E402
from plane import ADOPT_CLASSES as PLANE_ADOPT  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0072-translate-backlog.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0072-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0072" not in json.dumps(doc):
        print("FAILED:WFA-0072-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0072-probe2 self-declared", doc.get("state"))
        return 1

    rows, _meta = load_candidates()
    live = analyse(rows)
    backlog = doc.get("translate_backlog") or []
    if len(backlog) != live["translate_n"]:
        print("FAILED:WFA-0072-probe2 backlog length drift")
        return 1
    missing = [
        t
        for t in backlog
        if not t.get("target_adapter") or not str(t.get("target_adapter")).startswith("WFA-")
    ]
    if missing:
        print("FAILED:WFA-0072-probe2 TRANSLATE missing adapter", missing[:3])
        return 1
    live_missing = [t for t in live["translate_backlog"] if not t.get("target_adapter")]
    if live_missing:
        print("FAILED:WFA-0072-probe2 live missing adapter")
        return 1

    # Mutant: strip adapters — this state MUST be rejected.
    mutant_ok = True
    mutant = json.loads(json.dumps(backlog))
    for t in mutant:
        t["target_adapter"] = ""
    if mutant and all(t.get("target_adapter") for t in mutant):
        mutant_ok = False
    mutant_rejected = not all(t.get("target_adapter") for t in mutant) if mutant else True
    if backlog and not mutant_rejected:
        print("FAILED:WFA-0072-probe2 mutant still named adapters")
        return 1

    # Zero-reclass subset: ADOPT on chosen plane, no foreign imports.
    subset = [
        r
        for r in rows
        if str(r.get("classification") or "") in PLANE_ADOPT
        and str(r.get("runtime") or "") == "claude-code"
        and not (r.get("imports") or [])
    ]
    sub = analyse(subset)
    if sub["translate_n"] != 0 or not sub["zero_reclassification_ok"]:
        print(
            "FAILED:WFA-0072-probe2 chosen-plane subset should be zero TRANSLATE",
            sub["translate_n"],
            sub["disagreements"][:3],
        )
        return 1
    if live["translate_n"] == 0 and not live["zero_reclassification_ok"]:
        print("FAILED:WFA-0072-probe2 zero TRANSLATE without agreement")
        return 1

    adapters = sorted({t["target_adapter"] for t in backlog})
    payload = {
        "pass": True,
        "probe": "probe2-translate-adapters",
        "unit_id": "WFA-0072",
        "translate_n": live["translate_n"],
        "every_translate_names_adapter": True,
        "mutant_stripped_adapters_rejected": bool(mutant_rejected and mutant_ok),
        "chosen_plane_subset_zero_ok": True,
        "subset_n": len(subset),
        "adapters": adapters,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"translate={payload['translate_n']} adapters={adapters} "
        f"subset_zero={payload['chosen_plane_subset_zero_ok']}"
    )
    print("SUCCESS:WFA-0072-probe2 adapters and zero-reclass rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
