#!/usr/bin/env python3
"""Probe 2: negative control, recorded verbatim.

Rejected state: declared_outcome=irreducible-disagreement AND last-round
information gain still positive (and, separately, fatigue relabelled as
irreducible when gain has already collapsed but the evidence pack is a
budget/fatigue story).

On that planted-bad state the check FIRES. On the known-good collapsed
incommensurable state the same check is SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from irreducibility import attach_honest_trace, check_declaration  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md"
)
BAD = HERE / "fixtures/planted-bad.json"
GOOD = HERE / "fixtures/known-good.json"
FATIGUE = HERE / "fixtures/fatigue.json"

REJECTED_STATE = (
    "declared_outcome=irreducible-disagreement AND last-round information "
    "gain > 0 (keep-deliberating state relabelled as irreducible)"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_check(path: Path) -> dict:
    return check_declaration(attach_honest_trace(load(path)))


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0071-probe2 design note missing")
        return 1
    note = json.loads(ART.read_text(encoding="utf-8"))
    ncs = note.get("negative_controls") or []
    if not ncs:
        print("FAILED:CNL-0071-probe2 note has no negative_controls")
        return 1

    print(f"rejected_state={REJECTED_STATE}")

    bad = run_check(BAD)
    good = run_check(GOOD)
    fat = run_check(FATIGUE)

    bad_line = (
        "planted-bad "
        f"id=planted-bad-positive-gain fired={bad.get('fired')} "
        f"silent={bad.get('silent')} reason={bad.get('reason')} "
        f"last_gain={bad.get('last_gain')}"
    )
    good_line = (
        "known-good "
        f"id=known-good-collapsed-gain fired={good.get('fired')} "
        f"silent={good.get('silent')} accepted={good.get('accepted')} "
        f"reason={good.get('reason')}"
    )
    fat_line = (
        "fatigue-relabel "
        f"id=fatigue-zero-gain-budget-stop fired={fat.get('fired')} "
        f"silent={fat.get('silent')} reason={fat.get('reason')} "
        f"stop_reason={fat.get('stop_reason')}"
    )
    print(bad_line)
    print(good_line)
    print(fat_line)

    if not bad.get("fired") or bad.get("reason") != "positive-gain":
        print("FAILED:CNL-0071-probe2 check did not FIRE on the rejected state")
        return 1
    if good.get("fired") or not good.get("silent") or not good.get("accepted"):
        print("FAILED:CNL-0071-probe2 check was not SILENT on known-good")
        return 1
    if not fat.get("fired") or fat.get("reason") != "fatigue-relabel":
        print("FAILED:CNL-0071-probe2 fatigue relabel was not rejected")
        return 1

    recorded = json.dumps(ncs).lower()
    if "positive" not in recorded or "gain" not in recorded:
        print("FAILED:CNL-0071-probe2 note negative_control does not name positive gain")
        return 1

    print("negative_control_verbatim_bad=" + bad_line)
    print("negative_control_verbatim_good=" + good_line)
    print("SUCCESS:CNL-0071-probe2 both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
