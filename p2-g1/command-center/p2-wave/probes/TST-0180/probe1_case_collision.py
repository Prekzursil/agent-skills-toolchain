#!/usr/bin/env python3
"""TST-0180 probe1 -- case-distinct keys colliding under a case-insensitive parser
are detected and rejected naming both; a case-distinct non-colliding document
validates (both-states control).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import case_guard as CG  # noqa: E402

UNIT = "TST-0180"


def main() -> int:
    ok = None
    try:
        ok = CG.validate_strict(json.dumps({"hooks": {}, "commands": [], "name": "p"}))
    except CG.CaseCollisionError:
        pass

    err = None
    colliding_named: list[str] = []
    try:
        CG.validate_strict(json.dumps({"hooks": {"a": 1}, "Hooks": {"b": 2}}))
    except CG.CaseCollisionError as e:
        err = str(e)
        colliding_named = list(e.colliding)

    both_named = set(colliding_named) == {"hooks", "Hooks"}

    payload = {
        "probe": "probe1-case-collision",
        "unit_id": UNIT,
        "pass": ok is not None and err is not None and both_named,
        "distinct_keys_validate": ok is not None,
        "colliding_keys_rejected": err is not None,
        "both_keys_named_in_error": colliding_named,
        "error_text": err,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 distinct=valid collision=rejected named=%s"
              % (UNIT, colliding_named))
        return 0
    print("FAILED:%s-probe1 ok=%s err=%s named=%s"
          % (UNIT, ok is not None, err is not None, colliding_named))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
