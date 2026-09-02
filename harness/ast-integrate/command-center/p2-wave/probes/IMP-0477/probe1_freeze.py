#!/usr/bin/env python3
"""Named probe 1: freeze marker refuses in-place edits; no-down-step refused.

Signal 1: after freeze, writing a frozen schema/launcher is refused with
post-freeze-inplace-edit. Signal 2: a numbered migration missing its down-step
is refused with irreversible-migration. A path outside the freeze set stays
editable (both-states scope).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_broken_down_control  # noqa: E402
from scenario import run_freeze_scenario, run_irreversible_scenario  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0477.json"
SENTINEL = "SENTINEL:IMP-0477:MIGRATIONS-VERSIONED"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0477-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0477-probe1 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0477-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:IMP-0477-probe1 self-declared:{st}")
        return 1
    if doc.get("unit_id") != "IMP-0477":
        print("FAILED:IMP-0477-probe1 unit_id", doc.get("unit_id"))
        return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="imp0477-p1-") as tmp:
        root = Path(tmp)
        freeze = run_freeze_scenario(root / "freeze")
        irr = run_irreversible_scenario(root / "irr")
        broken = run_broken_down_control(root / "broken")

    payload = {
        "probe": "probe1-freeze-and-irreversible",
        "unit_id": "IMP-0477",
        "freeze": freeze,
        "irreversible": irr,
        "broken_down_control": broken,
        "pass": bool(
            freeze.get("pass") and irr.get("pass") and broken.get("pass")
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not freeze.get("pass"):
        print("FAILED:IMP-0477-probe1 freeze scenario")
        return 1
    if not irr.get("pass"):
        print("FAILED:IMP-0477-probe1 irreversible (no down-step) was not refused")
        return 1
    if not broken.get("pass"):
        print("FAILED:IMP-0477-probe1 no-op down-step was not caught")
        return 1
    print(
        "inplace_refused=%s code=%s no_down_refused=%s broken_down_caught=%s"
        % (
            freeze.get("inplace_refused"),
            freeze.get("inplace_code"),
            irr.get("refused"),
            broken.get("pass"),
        )
    )
    print("SUCCESS:IMP-0477-probe1 freeze refused in-place; no-down-step refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
