#!/usr/bin/env python3
"""Probe 1: path coverage both-states + every public execute path crosses the choke."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A3/SECURITY.json"


def main() -> int:
    both = C.both_states()
    print(f"live_ok={both['live_ok']} mutant_ok={both['mutant_ok']} both_states={both['both_states_pass']}")
    print(f"live_paths={both['live'].get('public_paths')}")
    print(f"mutant_sink_callers={both['mutant_sink_callers']}")
    if not both["both_states_pass"]:
        print("FAILED:ARC-0020-probe1 path-coverage both-states")
        return 1
    live = both["live"]
    if int(live["public_path_count"]) < 2 or int(live["sink_caller_count"]) != 1:
        print("FAILED:ARC-0020-probe1 coverage counts")
        return 1
    if live.get("forbidden_hits") != 0:
        print("FAILED:ARC-0020-probe1 public-fallback call present")
        return 1

    paths = S.run_all_public_paths()
    print(f"all_good_executed={paths['all_good_executed']} all_unsigned_refused={paths['all_unsigned_refused']}")
    if not paths["all_good_executed"] or not paths["all_unsigned_refused"]:
        print("FAILED:ARC-0020-probe1 public-path live run")
        return 1

    classes = S.run_class_controls()
    for k, v in classes.items():
        print(f"{k}={v}")
        if v is not True:
            print(f"FAILED:ARC-0020-probe1 {k}")
            return 1

    if not ART.is_file():
        print("FAILED:ARC-0020-probe1 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0020-probe1 self-declared {doc.get('state')}")
        return 1
    recorded = doc.get("path_coverage") or {}
    if recorded.get("all_execute_paths_cross_choke") is not True:
        print("FAILED:ARC-0020-probe1 artifact path_coverage incomplete")
        return 1
    if list(recorded.get("public_paths") or []) != list(live.get("public_paths") or []):
        print("FAILED:ARC-0020-probe1 artifact public_paths drift")
        return 1
    if int(recorded.get("public_path_count")) != int(live["public_path_count"]):
        print("FAILED:ARC-0020-probe1 artifact public_path_count drift")
        return 1
    if "SUCCESS:ARC-0020" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0020-probe1 sentinel absent")
        return 1
    print("SUCCESS:ARC-0020-probe1 path-coverage both-states class-controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
