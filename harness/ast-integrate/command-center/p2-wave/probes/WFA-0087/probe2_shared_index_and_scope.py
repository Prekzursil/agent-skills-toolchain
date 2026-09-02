#!/usr/bin/env python3
"""Probe 2: independent controls — shared-index fail, out-of-scope reject, sibling revert."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from executor import run_controls  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0087-repair-batch-execution.json"


def main() -> int:
    controls = run_controls()
    shared = controls["shared_index"]
    scope = controls["scope_sibling"]
    slim = {k: v for k, v in scope.items() if k != "poisoned_canary_output"}
    print(
        json.dumps(
            {"shared_index": shared, "scope_sibling": slim},
            sort_keys=True,
            default=str,
        )[:4000]
    )
    if not shared.get("contamination_detected"):
        print("FAILED:WFA-0087-probe2 shared-index contamination not detected")
        return 1
    if "b/workflow.py" not in shared.get("rejected_sibling_paths", []):
        print("FAILED:WFA-0087-probe2 sibling not in rejected staged set")
        return 1
    if not shared.get("ok"):
        print("FAILED:WFA-0087-probe2 shared-index control")
        return 1
    if not scope.get("poisoned_canary_red"):
        print("FAILED:WFA-0087-probe2 poisoned canary stayed green")
        return 1
    if not scope.get("poisoned_scope_rejected"):
        print("FAILED:WFA-0087-probe2 poisoned canary write not rejected by scope")
        return 1
    if not scope.get("restored_canary_green"):
        print("FAILED:WFA-0087-probe2 canary not restored green")
        return 1
    if not scope.get("target_still_green"):
        print("FAILED:WFA-0087-probe2 target not green after revert")
        return 1
    method = str(scope.get("restore_method") or "")
    if "checkout" in method.lower() and "no git checkout" not in method.lower():
        print("FAILED:WFA-0087-probe2 restore used checkout")
        return 1
    if not scope.get("ok") or not controls.get("ok"):
        print("FAILED:WFA-0087-probe2 controls not ok")
        return 1
    if OUT.is_file():
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        if doc.get("reviewer", {}).get("verdict") != "PASS":
            print("FAILED:WFA-0087-probe2 artifact reviewer not PASS")
            return 1
        if not doc.get("controls", {}).get("ok"):
            print("FAILED:WFA-0087-probe2 artifact controls not ok")
            return 1
        print("artifact_controls_ok=True")
    print("shared_index_rejected=True sibling_reverted=True scope_ok=True")
    print("SUCCESS:WFA-0087-probe2 shared-index and scope controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
