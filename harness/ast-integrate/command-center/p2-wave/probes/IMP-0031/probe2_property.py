#!/usr/bin/env python3
"""Named probe 2: unique-ours-line property + two-way-overwrite negative control.

Signal 2 of IMP-0031. Independent of the hand-authored fixture oracle (probe 1).
Reviewer adversarial triple (key reorder + comment) is checked here as well.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.ours_invariant import run_property  # noqa: E402
from plugin.three_way_merge import merge_bytes, merge_texts, two_way_overwrite  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0031.json"
N = 200
SEED = 31


def adversarial_reorder_comment() -> dict:
    base = '{\n  "alpha": 1,\n  "beta": 2\n}\n'
    ours = (
        "// owner: keep local timeout\n"
        "{\n  \"beta\": 2,\n  \"alpha\": 1,\n  \"timeout\": 30\n}\n"
    )
    theirs = '{\n  "alpha": 1,\n  "beta": 2,\n  "gamma": 3\n}\n'
    result = merge_texts(base, ours, theirs, path="settings.json")
    text = result.text or ""
    return {
        "status": result.status,
        "comment_survived": "// owner: keep local timeout" in text,
        "ours_timeout_survived": '"timeout": 30' in text,
        "theirs_gamma_survived": '"gamma": 3' in text,
        "pass": (
            result.status == "merged"
            and "// owner: keep local timeout" in text
            and '"timeout": 30' in text
            and '"gamma": 3' in text
        ),
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0031-probe2 receipt missing")
        return 1
    if "SUCCESS:IMP-0031" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0031-probe2 sentinel absent")
        return 1

    live = run_property(merge_bytes, n=N, seed=SEED)
    mutant = run_property(two_way_overwrite, n=N, seed=SEED)
    adv = adversarial_reorder_comment()

    report = {
        "probe": "probe2-property",
        "unit_id": "IMP-0031",
        "property": live,
        "negative_control_two_way_overwrite": mutant,
        "reviewer_adversarial_reorder_comment": adv,
    }
    print(json.dumps(report, sort_keys=True))

    if not live["ok"]:
        print("FAILED:IMP-0031-probe2 unique-ours property")
        return 1
    if mutant["ok"] or mutant["failures"] < 10:
        print(
            "FAILED:IMP-0031-probe2 negative control did not fail "
            f"(ok={mutant['ok']} failures={mutant['failures']})"
        )
        return 1
    if not adv["pass"]:
        print(f"FAILED:IMP-0031-probe2 adversarial triple {adv}")
        return 1
    print(
        f"property_ok=True samples={live['samples']} "
        f"overwrite_failures={mutant['failures']} adversarial_ok=True"
    )
    print("SUCCESS:IMP-0031-probe2 unique-ours property and two-way overwrite control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
