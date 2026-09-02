#!/usr/bin/env python3
"""Named probe 1: lint fires on planted omission; adjacent machine-readable scope passes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lint as L  # noqa: E402

FIXTURES = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def main() -> int:
    omit = L.lint_obj(load("verdict-omits-scope.json"))
    trail = L.lint_obj(load("verdict-trailing-limitations-only.json"))
    prose = L.lint_obj(load("verdict-prose-comment-scope.json"))
    ok = L.lint_obj(load("verdict-adjacent-scope.json"))

    omit_fire = (not omit["ok"]) and any(
        f.get("reason") == "scope-absent-not-adjacent" for f in omit["findings"]
    )
    trail_fire = (not trail["ok"]) and any(
        f.get("reason") == "scope-absent-not-adjacent" for f in trail["findings"]
    )
    prose_fire = (not prose["ok"]) and any(
        f.get("reason") == "scope-prose-not-machine-readable" for f in prose["findings"]
    )
    adjacent_pass = bool(ok["ok"]) and ok["verdicts_seen"] >= 1 and not ok["findings"]
    separated = omit_fire and trail_fire and prose_fire and adjacent_pass

    print(
        json.dumps(
            {
                "omit_fire": omit_fire,
                "omit_reasons": [f["reason"] for f in omit["findings"]],
                "trailing_limitations_fire": trail_fire,
                "trailing_reasons": [f["reason"] for f in trail["findings"]],
                "prose_fire": prose_fire,
                "prose_reasons": [f["reason"] for f in prose["findings"]],
                "adjacent_pass": adjacent_pass,
                "separated": separated,
            },
            sort_keys=True,
        )
    )
    if not omit_fire:
        print("FAILED:WFA-0097-probe1 planted omission did not fire")
        return 1
    if not trail_fire:
        print("FAILED:WFA-0097-probe1 trailing limitations scope was treated as adjacent")
        return 1
    if not prose_fire:
        print("FAILED:WFA-0097-probe1 prose scope was treated as machine-readable")
        return 1
    if not adjacent_pass:
        print("FAILED:WFA-0097-probe1 adjacent machine-readable scope was rejected")
        return 1
    print(
        "SUCCESS:WFA-0097-probe1 lint fires on omission/trailing/prose; "
        "adjacent machine-readable scope passes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
