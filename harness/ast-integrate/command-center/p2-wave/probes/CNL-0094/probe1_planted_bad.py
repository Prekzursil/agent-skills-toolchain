#!/usr/bin/env python3
"""Probe 1: planted-defect must FIRE; known-present is found before any absence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe1-planted-bad.raw.json"
ART_REL = "command-center/design/council/CNL-0094-evidence-free-majority-blocker.md"


def main() -> int:
    built = F.build_all()
    planted_order = [
        "planted-empty",
        "planted-fabricated",
        "planted-digest",
        "planted-support-mismatch",
    ]
    planted_results = []
    for name in planted_order:
        result = D.detect(built[name])
        planted_results.append(result)
        if not result["fired"]:
            print(f"FAILED:CNL-0094-probe1 planted {name} did not FIRE")
            print(json.dumps(result, sort_keys=True)[:2000])
            return 1
        if result["outcome"] != "REJECT":
            print(
                f"FAILED:CNL-0094-probe1 planted {name} outcome="
                f"{result['outcome']} want=REJECT (backed minority)"
            )
            return 1

    control_first = planted_results[0]
    if not control_first["fired"]:
        print("FAILED:CNL-0094-probe1 detector-control known-present missing")
        return 1

    good = D.detect(built["known-good-majority"])
    if not good["silent"]:
        print("FAILED:CNL-0094-probe1 known-good fired after control")
        return 1
    if good["outcome"] != "ADOPT":
        print(f"FAILED:CNL-0094-probe1 known-good outcome={good['outcome']}")
        return 1

    repo = D.repo_root()
    art = repo / ART_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CNL-0094-probe1 artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0094" not in text:
        print("FAILED:CNL-0094-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0094-probe1 self-declared {st}")
        return 1

    payload = {
        "probe": "probe1-planted-bad",
        "detector_control": {
            "known_present_found_before_absence": True,
            "order": ["planted-empty", "known-good-majority"],
            "planted_fired": True,
            "known_good_silent": True,
        },
        "planted": [
            {
                "fixture": r["council_id"],
                "fired": r["fired"],
                "outcome": r["outcome"],
                "raw_tally": r["raw_tally"],
                "counting_tally": r["counting_tally"],
                "n_counting": r["n_counting"],
            }
            for r in planted_results
        ],
        "known_good_after_control": {
            "fired": good["fired"],
            "silent": good["silent"],
            "outcome": good["outcome"],
        },
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True)[:3000])
    print(
        "fired_on_planted=4/4 known_present_first=True "
        f"known_good_silent={good['silent']} backed_minority_outcome=REJECT"
    )
    print("SUCCESS:CNL-0094-probe1 planted-bad FIRE and detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
