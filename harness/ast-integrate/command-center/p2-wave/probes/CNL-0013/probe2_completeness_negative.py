#!/usr/bin/env python3
"""Probe 2: explanation-completeness both-states + negative control.

FIRES when a non-default dial has an empty reason.
SILENT on a known-complete composition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from completeness import missing_reasons, plant_missing_reason  # noqa: E402
from rules import FIXTURES  # noqa: E402
from selector import select  # noqa: E402

REPO = HERE.parents[3]
NOTE = REPO / (
    "command-center/design/council/"
    "CNL-0013-auto-composed-council-the-selector-and-its-mandatory-expla.md"
)


def main() -> int:
    good_live = select(FIXTURES[4]["task_description"], FIXTURES[4]["risk_tier"])
    good_errs = missing_reasons(good_live)
    planted = plant_missing_reason(good_live)
    bad_errs = missing_reasons(planted)
    silent_on_good = good_errs == []
    fires_on_bad = any(e.startswith("missing-reason:") for e in bad_errs)
    print(f"live-good errors={good_errs or ['none']}")
    print(f"planted-bad errors={bad_errs}")
    print(f"fires_on_bad={fires_on_bad} silent_on_good={silent_on_good}")
    print(
        "negative-control: completeness FAILS a composition whose protocol "
        "differs from default and whose reason is empty; it is silent when "
        "every off-default dial carries a reason."
    )
    if not (fires_on_bad and silent_on_good):
        print("FAILED:CNL-0013-probe2 completeness did not discriminate")
        return 1

    if not NOTE.is_file():
        print("FAILED:CNL-0013-probe2 design-note-absent")
        return 1
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    fixtures = note.get("fixtures") or []
    if len(fixtures) < 10:
        print(f"FAILED:CNL-0013-probe2 note-fixture-count={len(fixtures)}")
        return 1
    expl = fixtures[4].get("explanation") or {}
    note_good = missing_reasons(expl)
    note_bad = missing_reasons(plant_missing_reason(expl))
    note_silent = note_good == []
    note_fires = any(e.startswith("missing-reason:") for e in note_bad)
    print(f"note-good errors={note_good or ['none']}")
    print(f"note-planted errors={note_bad}")
    print(f"note fires_on_bad={note_fires} silent_on_good={note_silent}")
    if not (note_fires and note_silent):
        print("FAILED:CNL-0013-probe2 note completeness did not discriminate")
        return 1

    print("SUCCESS:CNL-0013-probe2 completeness both-states negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
