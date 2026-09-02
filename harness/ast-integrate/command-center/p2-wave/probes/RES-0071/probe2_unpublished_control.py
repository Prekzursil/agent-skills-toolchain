#!/usr/bin/env python3
"""RES-0071 probe 2: NOT-PUBLISHED control is live, and both planted mutants go red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate import (  # noqa: E402
    OUT_REL,
    REPO,
    UNPUB,
    UNIT,
    check_doc,
    check_path,
    load_json,
    plant_numeric_without_citation,
    plant_strip_unpublished,
)


def main() -> int:
    path = REPO / OUT_REL
    live_errs = check_path(path)
    doc = load_json(path) if path.is_file() else {}
    systems = doc.get("systems") if isinstance(doc, dict) else None
    unpublished = [
        s.get("id")
        for s in (systems or [])
        if isinstance(s, dict) and s.get("accuracy_column") == UNPUB
    ]
    fake = plant_numeric_without_citation(doc) if isinstance(doc, dict) else {}
    stripped = plant_strip_unpublished(doc) if isinstance(doc, dict) else {}
    fake_errs = check_doc(fake)
    strip_errs = check_doc(stripped)
    live_ok = not live_errs
    fake_red = bool(fake_errs)
    strip_red = bool(strip_errs)
    both = live_ok and fake_red and strip_red and len(unpublished) >= 1
    payload = {
        "probe": "probe2-unpublished-control-both-states",
        "unit_id": UNIT,
        "live_ok": live_ok,
        "live_errors": live_errs,
        "unpublished_system_ids": unpublished,
        "unpublished_count": len(unpublished),
        "mutant_numeric_without_citation_red": fake_red,
        "mutant_numeric_errors": fake_errs[:8],
        "mutant_strip_unpublished_red": strip_red,
        "mutant_strip_errors": strip_errs[:8],
        "pass": both,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not both:
        print("FAILED:RES-0071-probe2 unpublished control or mutant silent")
        return 1
    print(
        "SUCCESS:RES-0071-probe2 live keeps NOT-PUBLISHED; "
        "numeric-without-citation and stripped-unpublished mutants go red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
