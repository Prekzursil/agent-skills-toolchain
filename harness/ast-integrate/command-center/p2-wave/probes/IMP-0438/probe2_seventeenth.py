#!/usr/bin/env python3
"""Named probe 2: adversarial 17th mutation + independent in-process instrument.

Probe 1 grades the CLI battery. This probe uses a different instrument
(in-process validate()) for M16, re-runs the historical disarmed surface so M16
is still the sole survivor there, and plants M17 (delete one defaults field)
which the original sixteen never included.

Pre-fix, M17 survived (103 unresolved timeout_seconds fields, SUCCESS). Post-fix
it is caught by the same V-FIELDS arming. That is expansion of coverage, not a
second unprotected hole.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))

import battery as B  # noqa: E402
import validate as val  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0438.json"


def inprocess_m16() -> dict:
    """Independent of battery.invoke: call validate() directly."""
    base = B.load_slim()
    tmp = Path("/tmp")
    # attach_register needs a writable dir; use a unique subdir via TemporaryDirectory
    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0438-p2-m16-") as raw:
        tdir = Path(raw)
        catalog = copy.deepcopy(base)
        fixture = B.attach_register(catalog, tdir)
        del catalog["defaults"]
        silent, silent_stats = val.validate(
            catalog, require_complete=False, register_path=fixture
        )
        armed, armed_stats = val.validate(
            catalog, require_complete=True, register_path=fixture
        )
        silent_checks = {v["check"] for v in silent}
        armed_checks = {v["check"] for v in armed}
        return {
            "unresolved": armed_stats.get("work_unit_fields_unresolved"),
            "disarmed_has_vfields": "V-FIELDS" in silent_checks,
            "armed_has_vfields": "V-FIELDS" in armed_checks,
            "disarmed_violation_count": len(silent),
            "armed_violation_count": len(armed),
            "silent_unresolved": silent_stats.get("work_unit_fields_unresolved"),
        }


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0438-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    survivor = doc.get("surviving_mutation") or {}
    if survivor.get("id") != "M16" or survivor.get("named_before_fix_written") is not True:
        print("FAILED:IMP-0438-probe2 receipt did not name M16 before the fix")
        return 1
    if "require_complete" not in str(survivor.get("unprotected_behavior") or ""):
        print("FAILED:IMP-0438-probe2 unprotected behavior not described")
        return 1

    disarmed = B.run_battery(B.MUTATIONS, disarm=True)
    m16 = next(r for r in disarmed["rows"] if r["id"] == "M16")
    m01 = next(r for r in disarmed["rows"] if r["id"] == "M01")
    if disarmed["survivor_ids"] != ["M16"]:
        print("FAILED:IMP-0438-probe2 disarmed survivors", disarmed["survivor_ids"])
        return 1
    if m16["caught"] or m16["exit_code"] != 0 or not m16["success_marker"]:
        print("FAILED:IMP-0438-probe2 disarmed M16 no longer reproduces the hole")
        return 1
    if not m01["caught"]:
        print("FAILED:IMP-0438-probe2 control mutation M01 was lost on the disarmed surface")
        return 1

    seventeenth = B.run_battery([B.SEVENTEENTH], disarm=False, include_control=True)
    m17 = seventeenth["rows"][0]
    if not m17["caught"] or not m17["claimed_check_in_output"]:
        print("FAILED:IMP-0438-probe2 M17 survived the armed battery; expand and fix")
        print(json.dumps(m17, indent=2)[:2000])
        return 1
    if seventeenth["control"].get("exit_code") != 0:
        print("FAILED:IMP-0438-probe2 M17 run broke CONTROL")
        return 1

    ip = inprocess_m16()
    if ip["disarmed_has_vfields"] or not ip["armed_has_vfields"]:
        print("FAILED:IMP-0438-probe2 in-process M16 both-states failed", ip)
        return 1
    if not ip["unresolved"] or ip["unresolved"] < 100:
        print("FAILED:IMP-0438-probe2 unresolved count too small", ip)
        return 1

    rec17 = doc.get("seventeenth_mutation") or {}
    if rec17.get("id") != "M17" or rec17.get("post_fix_caught") is not True:
        print("FAILED:IMP-0438-probe2 receipt M17 row missing or not caught post-fix")
        return 1
    if rec17.get("pre_fix_caught") is not False:
        print("FAILED:IMP-0438-probe2 receipt must record M17 survived pre-fix")
        return 1

    out = {
        "probe": "probe2-seventeenth",
        "unit_id": "IMP-0438",
        "disarmed_survivor_ids": disarmed["survivor_ids"],
        "m16_disarmed_exit": m16["exit_code"],
        "m01_still_caught_disarmed": m01["caught"],
        "m17_armed_caught": m17["caught"],
        "m17_check_in_output": m17["claimed_check_in_output"],
        "in_process_m16": ip,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"disarmed_survivor=M16 m17_caught={m17['caught']} "
        f"inprocess_armed_vfields={ip['armed_has_vfields']}"
    )
    print("SUCCESS:IMP-0438-probe2 seventeenth caught; M16 hole reproduced only when disarmed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
