#!/usr/bin/env python3
"""Probe 1: live discovery + NOT-CHECKED discipline + version capture.

Re-runs client discovery independently of the stored artifact and asserts the
artifact did not fold missing clients into a pass or take versions from docs.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import clients as C  # noqa: E402
import honesty as H  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0157.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 4000:
        print("FAILED:CNF-0157-probe1 artifact missing or tiny")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0157" not in text:
        print("FAILED:CNF-0157-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0157":
        print("FAILED:CNF-0157-probe1 unit_id", doc.get("unit_id"))
        return 1

    ok, why = H.check(doc)
    print(f"honesty_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0157-probe1 honesty")
        return 1

    live = C.discover()
    recorded_missing = list(doc.get("discovery", {}).get("missing_declared") or [])
    live_missing = list(live["missing_declared"])
    print(f"live_missing={live_missing} recorded_missing={recorded_missing}")
    if set(live_missing) != set(recorded_missing):
        print("FAILED:CNF-0157-probe1 missing-declared drift vs live PATH")
        return 1
    if live["catalog"]["tokens_present"] is not True:
        print("FAILED:CNF-0157-probe1 catalog tokens missing", live["catalog"])
        return 1

    live_pkg = live["plugin_package"]
    rec_pkg = (doc.get("discovery") or {}).get("plugin_package") or {}
    if live_pkg.get("production_present") != rec_pkg.get("production_present"):
        print(
            "FAILED:CNF-0157-probe1 plugin-package presence drift vs live "
            f"live={live_pkg.get('production_present')} "
            f"recorded={rec_pkg.get('production_present')}"
        )
        return 1
    if set(live_pkg.get("production_paths_present") or []) != set(
        rec_pkg.get("production_paths_present") or []
    ):
        print("FAILED:CNF-0157-probe1 production_paths_present drift vs live")
        return 1

    adj = live_pkg.get("adjacent_tools_plugin") or {}
    rec_adj = rec_pkg.get("adjacent_tools_plugin") or {}
    tools_dir = REPO / "tools/plugin"
    toolkit_not_package = tools_dir.is_dir() and not (
        (tools_dir / "plugin.json").is_file()
        and C._manifest_is_client_plugin(tools_dir / "plugin.json")
    )
    if toolkit_not_package:
        if "tools/plugin" in (live_pkg.get("production_paths_present") or []):
            print("FAILED:CNF-0157-probe1 production plugin unexpectedly present")
            return 1
        if "tools/plugin" in (rec_pkg.get("production_paths_absent") or []):
            print(
                "FAILED:CNF-0157-probe1 tools/plugin listed absent while "
                "Python toolkit directory exists"
            )
            return 1
        if rec_adj.get("exists") is not True or adj.get("exists") is not True:
            print("FAILED:CNF-0157-probe1 adjacent tools/plugin existence not recorded")
            return 1
        if rec_adj.get("is_loadable_plugin_package") is True:
            print("FAILED:CNF-0157-probe1 toolkit misrecorded as loadable plugin")
            return 1
    if live_pkg.get("production_present") is True:
        for cell in doc.get("cells") or []:
            if (
                cell.get("surface") == "live-client"
                and cell.get("verdict") == "REPRODUCES"
            ):
                print(
                    "FAILED:CNF-0157-probe1 production plugin present but "
                    "live cell folded to REPRODUCES"
                )
                return 1

    live_cells = [
        c for c in doc["cells"] if c.get("surface") == "live-client"
    ]
    not_checked = [c for c in live_cells if c.get("verdict") == "NOT-CHECKED"]
    if len(not_checked) != len(live_cells) or len(live_cells) != 16:
        print(
            f"FAILED:CNF-0157-probe1 live cells not all NOT-CHECKED "
            f"{len(not_checked)}/{len(live_cells)}"
        )
        return 1
    for cell in live_cells:
        if cell.get("version_source") == "not-installed" and not cell.get("prerequisite"):
            print("FAILED:CNF-0157-probe1 prerequisite unnamed", cell.get("id"))
            return 1

    mutant = copy.deepcopy(doc)
    flipped = False
    for cell in mutant["cells"]:
        if (
            cell.get("surface") == "live-client"
            and cell.get("verdict") == "NOT-CHECKED"
        ):
            cell["verdict"] = "REPRODUCES"
            flipped = True
            break
    if not flipped:
        print("FAILED:CNF-0157-probe1 no NOT-CHECKED cell to mutate")
        return 1
    mok, mwhy = H.check(mutant)
    print(f"mutant_live_pass_ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0157-probe1 mutant that folded NOT-CHECKED into REPRODUCES was accepted")
        return 1

    extra = live["extra_runtimes"]
    print(f"extra_runtimes={len(extra)}")
    for row in extra:
        if row.get("folded_into_matrix_pass"):
            print("FAILED:CNF-0157-probe1 extra runtime folded into pass")
            return 1

    print(
        "SUCCESS:CNF-0157-probe1 live-matrix NOT-CHECKED discipline "
        f"missing={live_missing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
