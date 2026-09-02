#!/usr/bin/env python3
"""Probe 2: detector control — a capability rename MUST be visible.

Plant a trivial id/name rename of cap.git-status. The live comparator
must see a top-k change. A stub that always reports identical routing
must miss that change (known-broken fixture).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_rename_detector  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0215.json"


def main() -> int:
    det = run_rename_detector()
    print(json.dumps(
        {
            "probe": "probe2-rename-detector",
            "detected": det["detected"],
            "n_tasks_changed": det["n_tasks_changed"],
            "n_git_tasks_changed": det["n_git_tasks_changed"],
            "stub_always_equal_misses": det["stub_always_equal_misses"],
            "stub_is_known_broken": det["stub_is_known_broken"],
            "rename": det["rename"],
            "sample": det["sample"],
            "pass": det["pass"],
        },
        sort_keys=True,
    ))
    if not det["detected"]:
        print("FAILED:TST-0215-probe2 rename comparison was silent")
        return 1
    if det["n_git_tasks_changed"] < 1:
        print("FAILED:TST-0215-probe2 no git-status task changed after rename")
        return 1
    if not det["stub_is_known_broken"]:
        print("FAILED:TST-0215-probe2 stub comparator did not miss the rename")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        live = (doc.get("live_measurements") or {}).get("rename_detector") or {}
        if live.get("detected") is False:
            print("FAILED:TST-0215-probe2 artifact claims detector did not fire")
            return 1
    print("SUCCESS:TST-0215-probe2 rename detector fired; stub always-equal missed it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
