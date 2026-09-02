#!/usr/bin/env python3
"""Probe 2: RUN requires an inside-client observation, never an installer exit."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage_gate as G  # noqa: E402
import simulate_inside_client as S  # noqa: E402
import test_coverage_gate as T  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0006.json"
GOOD = HERE / "fixtures" / "plugin.good.json"
CORRUPT = HERE / "fixtures" / "plugin.corrupt.json"
UNLOADED = "plugin-appears-installed-but-hooks-unloaded"


def both_states() -> int:
    green = S.probe_plugin(GOOD)
    red = S.probe_plugin(CORRUPT)
    print(
        f"both-states good ok={green['ok']} reason={green['reason']} "
        f"corrupt ok={red['ok']} reason={red['reason']}"
    )
    if not green["ok"] or not green["hook_fired"] or not green["command_resolved"]:
        print("FAILED:BLD-0006-probe2 good manifest did not produce inside-client obs")
        return 1
    if red["ok"] or not red["red"]:
        print(
            "FAILED:BLD-0006-probe2 corrupt manifest stayed green — probe measures nothing"
        )
        return 1
    if red["reason"] == green["reason"]:
        print("FAILED:BLD-0006-probe2 both states same reason")
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0006-corrupt-") as tmp:
        live = Path(tmp) / "plugin.json"
        live.write_text(GOOD.read_text(encoding="utf-8"), encoding="utf-8")
        before = S.probe_plugin(live)
        doc = json.loads(live.read_text(encoding="utf-8"))
        doc["hooks"] = []
        live.write_text(json.dumps(doc), encoding="utf-8")
        after = S.probe_plugin(live)
        print(
            f"deliberate-corrupt before_ok={before['ok']} after_ok={after['ok']} "
            f"after_reason={after['reason']}"
        )
        if not before["ok"] or after["ok"]:
            print("FAILED:BLD-0006-probe2 deliberate corrupt did not turn RUN probe red")
            return 1
        if after["failure_class"] != UNLOADED:
            print(f"FAILED:BLD-0006-probe2 wrong failure class {after['failure_class']}")
            return 1
    return 0


def live_cells() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0006-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    cells = doc.get("cells") or []
    findings = G.validate_matrix(cells)
    if findings:
        print("FAILED:BLD-0006-probe2 live matrix failed evidence gate")
        print(json.dumps(findings[:6], indent=2))
        return 1
    for cell in cells:
        if cell.get("status") == "RUN" and G.installer_only(cell):
            print(f"FAILED:BLD-0006-probe2 installer-only RUN {cell.get('id')}")
            return 1
        if cell.get("client_present") is False and cell.get("status") != "NOT-CHECKED":
            print(f"FAILED:BLD-0006-probe2 absent not NOT-CHECKED {cell.get('id')}")
            return 1
        if cell.get("status") in {"PASS", "FAIL"}:
            print(f"FAILED:BLD-0006-probe2 forbidden status {cell.get('status')}")
            return 1
    print(f"live_cells={len(cells)} gate_ok=True")
    return 0


def main() -> int:
    T.test_installer_exit_only_rejected()
    T.test_absent_client_is_not_checked()
    T.test_absent_without_install_step_fails()
    print("control installer-exit-only rejected; absent client NOT-CHECKED")
    rc = both_states()
    if rc:
        return rc
    rc = live_cells()
    if rc:
        return rc
    print("SUCCESS:BLD-0006-probe2 inside-client observation and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
