#!/usr/bin/env python3
"""Probe 2: sandbox owner-gate — marker appears only inside the sandbox.

Mechanically independent of probe 1 (direct subprocess): this probe drives
install_package with an explicit owner gate and a sandbox root distinct from
dest. Parent TST0217_HOST_MARKER must not leak. The installer output must
name scripts.postinstall and its handling.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.install import (  # noqa: E402
    HANDLING_GATE_NO_SANDBOX,
    HANDLING_REFUSED_IMPLICIT,
    HANDLING_SANDBOX_GATED,
    SCRIPT_FIELD,
    measure_postinstall_policy,
)

RECEIPT = REPO / "command-center" / "receipts" / "TST-0217.json"
SENTINEL = "SUCCESS:TST-0217"


def _receipt_ok() -> bool | None:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    ev = doc.get("evidence_requirement") or {}
    declared = ev.get("b_installer_declared_script_handling") or {}
    sand = ev.get("sandbox_both_states") or {}
    return (
        str(doc.get("state") or "").upper()
        not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
        and SENTINEL in text
        and declared.get("script_field") == SCRIPT_FIELD
        and declared.get("implicit_handling") == HANDLING_REFUSED_IMPLICIT
        and declared.get("sandbox_handling") == HANDLING_SANDBOX_GATED
        and sand.get("sandbox_marker_present") is True
        and sand.get("sandbox_dest_marker_present") is False
        and sand.get("leaked_host_marker_present") is False
    )


def main() -> int:
    live = measure_postinstall_policy()
    receipt_ok = _receipt_ok()
    gated = live.get("sandbox_owner_gated") or {}
    implicit = live.get("implicit_install") or {}
    no_sbx = live.get("owner_gate_without_sandbox") or {}
    ok = (
        bool(live.get("pass"))
        and bool(live.get("sandbox_pass"))
        and gated.get("handling") == HANDLING_SANDBOX_GATED
        and gated.get("script_field") == SCRIPT_FIELD
        and implicit.get("handling") == HANDLING_REFUSED_IMPLICIT
        and implicit.get("script_field") == SCRIPT_FIELD
        and no_sbx.get("handling") == HANDLING_GATE_NO_SANDBOX
        and live.get("sandbox_marker_present") is True
        and live.get("sandbox_dest_marker_present") is False
        and live.get("leaked_host_marker_present") is False
        and (receipt_ok is not False)
    )
    payload = {
        "probe": "probe2-sandbox-both-states",
        "unit_id": "TST-0217",
        "method": "install_package-owner-gate-sandbox",
        "data_field": "sandbox_marker_present+dest_marker_absent+declared_handling",
        "measurement_kind": "sandbox-owner-gated-vs-implicit-refuse",
        "pass": ok,
        "live": {
            "script_field": gated.get("script_field"),
            "sandbox_handling": gated.get("handling"),
            "sandbox_execution_location": gated.get("execution_location"),
            "host_marker_env_passed": gated.get("host_marker_env_passed"),
            "sandbox_marker_present": live.get("sandbox_marker_present"),
            "sandbox_dest_marker_present": live.get("sandbox_dest_marker_present"),
            "leaked_host_marker_present": live.get("leaked_host_marker_present"),
            "implicit_handling": implicit.get("handling"),
            "owner_gate_without_sandbox_handling": no_sbx.get("handling"),
            "both_states": live.get("both_states"),
            "pass": live.get("pass"),
        },
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if gated.get("handling") != HANDLING_SANDBOX_GATED:
        print(f"FAILED:TST-0217-probe2 sandbox handling={gated.get('handling')}")
        return 1
    if gated.get("script_field") != SCRIPT_FIELD:
        print("FAILED:TST-0217-probe2 installer did not declare scripts.postinstall")
        return 1
    if not live.get("sandbox_marker_present"):
        print("FAILED:TST-0217-probe2 sandbox marker absent")
        return 1
    if live.get("sandbox_dest_marker_present"):
        print("FAILED:TST-0217-probe2 host dest received the sandbox marker")
        return 1
    if live.get("leaked_host_marker_present"):
        print("FAILED:TST-0217-probe2 parent HOST_MARKER leaked through sandbox")
        return 1
    if implicit.get("handling") != HANDLING_REFUSED_IMPLICIT:
        print(f"FAILED:TST-0217-probe2 implicit handling={implicit.get('handling')}")
        return 1
    if no_sbx.get("handling") != HANDLING_GATE_NO_SANDBOX:
        print("FAILED:TST-0217-probe2 owner gate without sandbox executed or mis-declared")
        return 1
    if receipt_ok is False:
        print("FAILED:TST-0217-probe2 receipt does not match live sandbox measurement")
        return 1
    print(
        f"sandbox_marker={live.get('sandbox_marker_present')} "
        f"dest_marker={live.get('sandbox_dest_marker_present')} "
        f"handling={gated.get('handling')} field={gated.get('script_field')}"
    )
    print("SUCCESS:TST-0217-probe2 sandbox gate writes marker only inside the sandbox")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
