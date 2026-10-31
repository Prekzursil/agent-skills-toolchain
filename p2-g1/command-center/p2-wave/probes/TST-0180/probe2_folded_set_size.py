#!/usr/bin/env python3
"""TST-0180 probe2 -- independent case-folded key-set size vs raw key-set size,
plus emitter never-collides property and a last-wins detector control.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import case_guard as CG  # noqa: E402

UNIT = "TST-0180"


def main() -> int:
    # independent signal: case-folded set size vs raw set size over a colliding doc
    doc_keys = ["hooks", "Hooks", "HOOKS", "commands", "agents"]
    raw_n = len(set(doc_keys))
    folded_n = len(set(k.casefold() for k in doc_keys))
    fold_delta = raw_n - folded_n  # 3 colliding forms -> delta 2

    # emitter property: random field-name permutations never collide on emit
    rng = random.Random(180180)
    universe = ["name", "version", "hooks", "skills", "commands", "agents", "license"]
    emitter_clean = True
    for _ in range(300):
        n = rng.randint(1, len(universe))
        fields = {rng.choice(universe): 1 for _ in range(n)}  # raw dict dedups exact dupes
        try:
            CG.emit_safe(fields)
        except CG.CaseCollisionError:
            emitter_clean = False
    # emitter refuses a constructed collision
    refused = False
    try:
        CG.emit_safe({"hooks": 1, "Hooks": 2})
    except CG.CaseCollisionError:
        refused = True

    # detector control: python's own json parser is LAST-KEY-WINS on exact dupes,
    # and a case-insensitive consumer would silently drop "Hooks" vs "hooks"
    last_wins = json.loads('{"hooks": 1, "hooks": 2}') == {"hooks": 2}

    payload = {
        "probe": "probe2-folded-set-size",
        "unit_id": UNIT,
        "pass": fold_delta == 2 and emitter_clean and refused and last_wins,
        "folded_set_comparison": {
            "raw_distinct": raw_n,
            "casefolded_distinct": folded_n,
            "delta_is_collision_count": fold_delta,
        },
        "emitter": {
            "clean_over_300_generated": emitter_clean,
            "refuses_constructed_collision": refused,
        },
        "detector_control": {
            "known_broken": "json last-key-wins dedup (exact) / case-insensitive consumer (fold)",
            "last_wins_confirmed": last_wins,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 fold_delta=%d emitter_clean=%s last_wins=%s"
              % (UNIT, fold_delta, emitter_clean, last_wins))
        return 0
    print("FAILED:%s-probe2 delta=%d emitter=%s refused=%s lastwins=%s"
          % (UNIT, fold_delta, emitter_clean, refused, last_wins))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
