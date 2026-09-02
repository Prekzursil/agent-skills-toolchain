#!/usr/bin/env python3
"""Probe 2: both-states plant/revert + Stop-hook latency.

Plant a one-line edit in a live-tree copy, assert the detector fires and the
Stop-hook surfaces a warning; revert and assert silence.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import stop_hook as H  # noqa: E402
import trees as T  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"
PLANT = "ARC-0005-PLANTED-EDIT\n"
TARGET = T.CTRL_LIVE / "common/control.md"


def main() -> int:
    T.build_control_fixtures()
    if TARGET.exists() and PLANT in TARGET.read_text(encoding="utf-8"):
        TARGET.write_text(TARGET.read_text(encoding="utf-8").replace(PLANT, ""), encoding="utf-8")

    good = D.detect(T.CTRL_REPO, T.CTRL_LIVE)
    H.run(T.CTRL_REPO, T.CTRL_LIVE)
    if not good["silent"]:
        print("FAILED:ARC-0005-probe2 baseline not silent", good)
        return 1
    if H.SURFACE.is_file():
        print("FAILED:ARC-0005-probe2 warning present on good state")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    t0 = time.perf_counter()
    TARGET.write_text(original + PLANT, encoding="utf-8")
    planted_ns = time.time_ns()
    bad = D.detect(T.CTRL_REPO, T.CTRL_LIVE)
    hook = H.run(T.CTRL_REPO, T.CTRL_LIVE)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0
    warning_ok = H.SURFACE.is_file() and "DRIFT WARNING" in H.SURFACE.read_text(encoding="utf-8")
    if not bad["fired"] or not hook["fired"] or not warning_ok:
        TARGET.write_text(original, encoding="utf-8")
        print("FAILED:ARC-0005-probe2 detector or stop-hook did not fire")
        return 1

    TARGET.write_text(original, encoding="utf-8")
    restored = D.detect(T.CTRL_REPO, T.CTRL_LIVE)
    H.run(T.CTRL_REPO, T.CTRL_LIVE)
    if not restored["silent"] or H.SURFACE.is_file():
        print("FAILED:ARC-0005-probe2 revert did not go silent")
        return 1

    doc = {
        "fired_on_bad": True,
        "silent_on_good": True,
        "silent_after_revert": True,
        "stop_hook_warning_on_bad": True,
        "stop_hook_silent_on_good": True,
        "latency_ms": round(latency_ms, 3),
        "planted_ns": planted_ns,
        "stop_hook_path": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad=True silent_on_good=True revert_silent=True "
        f"latency_ms={doc['latency_ms']} stop_hook=stop_hook.py"
    )
    print("SUCCESS:ARC-0005-probe2 both-states and stop-hook latency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
