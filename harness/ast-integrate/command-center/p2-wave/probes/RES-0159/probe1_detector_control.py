#!/usr/bin/env python3
"""Named probe 1: plant 3 verbatim briefing restatements; subtractor must drop all 3.

Both-states: three synthetic novel edges must survive. A skip-subtract mutant
must let the restatements survive (otherwise the control is one-sided).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import subtractor as S  # noqa: E402

ART = S.REPO / S.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0159-probe1 {msg}")
    return 1


def main() -> int:
    measured = S.measure()
    ok, why = S.detector_ok(measured)
    plants = [t.as_dict() for t in measured["plants"]]
    novels = [t.as_dict() for t in measured["novels"]]
    payload = {
        "probe": "probe1-detector-control",
        "unit_id": "RES-0159",
        "planted_restatements": plants,
        "planted_n": len(plants),
        "survived_restatements": [t.as_dict() for t in measured["survived_plants"]],
        "all_restatements_removed": len(measured["survived_plants"]) == 0,
        "novel_plants": novels,
        "novel_plants_survived": len(measured["survived_novels"]),
        "skip_subtract_mutant_survives_plants": len(
            measured["mutant_skip_subtract_survived"]
        )
        == 3,
        "pass": False,
    }
    if not ok:
        payload["reason"] = why
        print(json.dumps(payload, sort_keys=True))
        return fail(why)
    if not ART.is_file() or ART.stat().st_size <= 0:
        print(json.dumps(payload, sort_keys=True))
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if S.SENTINEL not in text:
        return fail("SUCCESS:RES-0159 absent from artifact")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    control = doc.get("detector_control") or {}
    if control.get("planted_restatements") != 3 or control.get("survived") != 0:
        return fail(f"artifact detector_control mismatch {control}")
    if control.get("all_removed") is not True:
        return fail("artifact all_removed is not true")
    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True))
    print(
        "plants_removed=3 novel_survived=3 skip_subtract_mutant_would_keep=3"
    )
    print("SUCCESS:RES-0159-probe1 detector control removes 3 restatements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
