#!/usr/bin/env python3
"""Named probe 2: moderator-capture both-states + independent presence.

Skewed chair (never recognises the dissenter) must FIRE.
Even chair (fair round-robin) must stay SILENT.
Dissenter submissions still appear in the artifact when unrecognised.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import RECEIPT, evaluate_probe2  # noqa: E402

ART = REPO / RECEIPT


def main() -> int:
    result = evaluate_probe2()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0282-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0282" not in text:
        print("FAILED:IMP-0282-probe2 sentinel absent")
        return 1
    if not result["pass"]:
        print("FAILED:IMP-0282-probe2 moderator-capture both-states")
        return 1
    print(
        f"fire_on_skew={result['fire_on_skew']} "
        f"silent_on_even={result['silent_on_even']} "
        f"drew_subs={result['dissenter_submissions']['artifact_submissions']} "
        f"drew_recs={result['dissenter_submissions']['recognitions']}"
    )
    print(
        "SUCCESS:IMP-0282-probe2 skewed chair FIRE, even chair SILENT, "
        "unrecognised submissions present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
