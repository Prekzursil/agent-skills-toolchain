#!/usr/bin/env python3
"""Named probe 1: fire-and-forget profile refused; blocking twin imports.

Both-states: the background-flagged fixture raises a closed reason_id;
the twin (same units, no background / fire_and_forget) imports as a typed
Workflow whose FanOut width matches the fixture unit count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(REPO / "tools" / "import-adapters"))

from agentspec import argv  # noqa: E402
from codex_fanout import ImportRefused, import_fanout_path  # noqa: E402

FIRE_REASONS = frozenset({"dispatch.background-flagged", "dispatch.fire-and-forget"})


def _load_import(name: str):
    path = HERE / "fixtures" / name
    try:
        wf = import_fanout_path(path)
        return {"ok": True, "workflow": wf, "reason_id": None}
    except ImportRefused as exc:
        return {"ok": False, "workflow": None, "reason_id": exc.reason_id}


def main() -> int:
    bad = _load_import("fire-and-forget.json")
    good = _load_import("blocking-twin.json")
    missing = _load_import("missing-timeout.json")
    prompt = _load_import("prompt-on-argv.json")

    if bad["ok"] or bad["reason_id"] not in FIRE_REASONS:
        print(
            "FAILED:IMP-0161-probe1 fire-and-forget was not refused with a named "
            f"dispatch reason; ok={bad['ok']} reason_id={bad['reason_id']!r}"
        )
        return 1
    if not good["ok"] or not isinstance(good["workflow"], dict):
        print(
            "FAILED:IMP-0161-probe1 blocking twin did not import; "
            f"ok={good['ok']} reason_id={good['reason_id']!r}"
        )
        return 1

    wf = good["workflow"]
    nodes = wf.get("nodes") or []
    fanouts = [n for n in nodes if isinstance(n, dict) and n.get("kind") == "FanOut"]
    barriers = [n for n in nodes if isinstance(n, dict) and n.get("kind") == "Barrier"]
    if len(fanouts) != 1 or len(barriers) != 1:
        print(f"FAILED:IMP-0161-probe1 expected FanOut+Barrier, got {wf.get('nodes')}")
        return 1
    units = fanouts[0].get("units") or []
    if fanouts[0].get("width") != 2 or len(units) != 2:
        print(f"FAILED:IMP-0161-probe1 fan-out width not preserved: {fanouts[0]}")
        return 1

    fixture = json.loads((HERE / "fixtures" / "blocking-twin.json").read_text(encoding="utf-8"))
    for src, planned in zip(fixture["units"], units):
        expected = list(
            argv.build(
                fixture["binary"],
                prompt_file=src["prompt_file"],
                timeout_seconds=fixture["timeout_seconds"],
            )
        )
        if planned.get("argv") != expected:
            print(
                "FAILED:IMP-0161-probe1 argv does not match agentspec.argv.build "
                f"unit={src['id']} got={planned.get('argv')!r} expected={expected!r}"
            )
            return 1
        if "--prompt-file" not in planned["argv"]:
            print("FAILED:IMP-0161-probe1 prompt was not routed off argv")
            return 1
        if src["prompt_file"] not in planned["argv"]:
            print("FAILED:IMP-0161-probe1 prompt_file missing from argv")
            return 1
        joined = " ".join(planned["argv"])
        if "inline prompt" in joined:
            print("FAILED:IMP-0161-probe1 prompt body leaked onto argv")
            return 1

    if missing["ok"] or missing["reason_id"] != "dispatch.missing-timeout":
        print(
            "FAILED:IMP-0161-probe1 missing-timeout not refused; "
            f"ok={missing['ok']} reason_id={missing['reason_id']!r}"
        )
        return 1
    if prompt["ok"] or prompt["reason_id"] != "dispatch.prompt-on-argv":
        print(
            "FAILED:IMP-0161-probe1 prompt-on-argv not refused; "
            f"ok={prompt['ok']} reason_id={prompt['reason_id']!r}"
        )
        return 1

    # Detector control: flipping background off on the bad fixture must import;
    # flipping it on the twin must refuse. Proves the flag is the discriminator.
    flipped_bad = json.loads((HERE / "fixtures" / "fire-and-forget.json").read_text(encoding="utf-8"))
    flipped_bad["background"] = False
    flipped_bad["fire_and_forget"] = False
    from codex_fanout import import_fanout_profile

    try:
        import_fanout_profile(flipped_bad)
        flag_off_imports = True
    except ImportRefused:
        flag_off_imports = False
    flipped_good = json.loads((HERE / "fixtures" / "blocking-twin.json").read_text(encoding="utf-8"))
    flipped_good["background"] = True
    try:
        import_fanout_profile(flipped_good)
        flag_on_imports = True
        flag_on_reason = None
    except ImportRefused as exc:
        flag_on_imports = False
        flag_on_reason = exc.reason_id
    if not flag_off_imports or flag_on_imports or flag_on_reason not in FIRE_REASONS:
        print(
            "FAILED:IMP-0161-probe1 both-states discriminator failed "
            f"flag_off_imports={flag_off_imports} flag_on_imports={flag_on_imports} "
            f"flag_on_reason={flag_on_reason!r}"
        )
        return 1

    out = {
        "probe": "probe1-refuse-fire-and-forget",
        "unit_id": "IMP-0161",
        "pass": True,
        "fire_and_forget_refused": True,
        "reason_id": bad["reason_id"],
        "blocking_twin_imported": True,
        "fanout_width": fanouts[0]["width"],
        "argv_matches_agentspec": True,
        "missing_timeout_reason_id": missing["reason_id"],
        "prompt_on_argv_reason_id": prompt["reason_id"],
        "both_states": {
            "flag_off_imports": flag_off_imports,
            "flag_on_refused": not flag_on_imports,
            "flag_on_reason": flag_on_reason,
        },
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"refused={bad['reason_id']} twin_width={fanouts[0]['width']} "
        f"timeout={missing['reason_id']} prompt={prompt['reason_id']}"
    )
    print("SUCCESS:IMP-0161-probe1 fire-and-forget refused; blocking twin imported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
