#!/usr/bin/env python3
"""Probe 2: post-fix silence, planted regression, held-out reviewer mention.

Catalog tests_required:
  * Post-fix: the corrected checklist line must be silent while a planted
    regression re-fires.
Reviewer requirement:
  * An independent reviewer supplies a new documentary mention (text the
    author never put in the labelled control set) and the discriminator
    still holds.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE_PATH = REPO / "command-center" / "wrong_recipe_gate.py"
ART = REPO / "command-center/receipts/CC-0006.json"


def load_gate():
    spec = importlib.util.spec_from_file_location("wrong_recipe_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("FAILED:CC-0006-probe2 cannot load gate")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    g = load_gate()

    live = REPO / "command-center/RELEASE-CHECKLIST.md"
    if not live.is_file():
        print("FAILED:CC-0006-probe2 live RELEASE-CHECKLIST.md missing")
        return 1
    live_hits = g.scan_path(live, REPO)
    live_bad = g.prescriptive(live_hits)
    print(
        f"postfix_checklist_prescriptive={len(live_bad)} "
        f"archive_lines={len(live_hits)}"
    )
    if live_bad:
        print("FAILED:CC-0006-probe2 corrected checklist still fires")
        print(live_bad)
        return 1
    body = live.read_text(encoding="utf-8")
    if "git cat-file" not in body:
        print("FAILED:CC-0006-probe2 corrected checklist does not prescribe cat-file")
        return 1
    if "git archive" not in body.lower():
        print(
            "FAILED:CC-0006-probe2 corrected checklist dropped the mention; "
            "use-vs-mention on the live line is then untested"
        )
        return 1

    planted = HERE / "fixtures/planted-regression.md"
    plant_hits = g.scan_path(planted, REPO)
    plant_bad = g.prescriptive(plant_hits)
    print(f"planted_regression_prescriptive={len(plant_bad)}")
    if not plant_bad:
        print("FAILED:CC-0006-probe2 planted regression did not re-fire")
        print(plant_hits)
        return 1

    held = HERE / "fixtures/reviewer-heldout-documentary.md"
    held_text = held.read_text(encoding="utf-8")
    # Held-out text must not be a labelled control (independence).
    labelled = {t for t, _ in g.LABELLED_CONTROLS}
    if held_text.strip() in labelled:
        print("FAILED:CC-0006-probe2 held-out text is a labelled control")
        return 1
    held_hits = g.scan_path(held, REPO)
    held_bad = g.prescriptive(held_hits)
    print(
        f"reviewer_heldout_prescriptive={len(held_bad)} "
        f"archive_lines={len(held_hits)}"
    )
    if held_bad:
        print("FAILED:CC-0006-probe2 reviewer documentary mention fired")
        print(held_bad)
        return 1
    if not held_hits:
        print("FAILED:CC-0006-probe2 reviewer text did not mention git archive")
        return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CC-0006-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:CC-0006-probe2 receipt self-declared {doc.get('state')}")
        return 1
    raw = ART.read_text(encoding="utf-8")
    if "SUCCESS:CC-0006" not in raw:
        print("FAILED:CC-0006-probe2 sentinel absent")
        return 1

    print("SUCCESS:CC-0006-probe2 postfix planted-regression reviewer-heldout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
