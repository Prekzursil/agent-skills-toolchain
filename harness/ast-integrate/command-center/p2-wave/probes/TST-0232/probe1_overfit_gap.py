#!/usr/bin/env python3
"""Probe 1: fixture-overfit candidate must fire; honest candidate must not.

Mechanically: live gate.evaluate on both predictors. Does not read provenance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import corpus as K  # noqa: E402
import gate as G  # noqa: E402

ART = REPO / C.OUTPUT_REL
UNIT = C.UNIT_ID


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    corpus = K.build_corpus()
    live = G.both_states(corpus["visible"], corpus["holdout"])
    honest, overfit = live["honest"], live["overfit"]
    payload = {
        "probe": "probe1-overfit-gap",
        "unit_id": UNIT,
        "honest": G.compact(honest),
        "overfit": G.compact(overfit),
        "overfit_fired": live["overfit_fired"],
        "honest_silent": live["honest_silent"],
        "threshold": live["threshold"],
        "n_visible": len(corpus["visible"]),
        "n_holdout": len(corpus["holdout"]),
        "pass": live["overfit_fired"] and live["honest_silent"],
    }
    print(json.dumps(payload, sort_keys=True))
    if honest["verdict"] != "PASS":
        return fail(f"honest verdict {honest['verdict']!r}")
    if overfit["verdict"] != "FAIL_GAMING":
        return fail(f"overfit verdict {overfit['verdict']!r} (detector silent)")
    if honest["visible_score"] != 1.0 or honest["holdout_score"] != 1.0:
        return fail("honest did not score 1.0 on both splits")
    if overfit["visible_score"] != 1.0:
        return fail("overfit did not memorize the visible split")
    if overfit["holdout_score"] != 0.0:
        return fail("overfit unexpectedly scored holdout")
    if overfit["gap"] <= C.GAP_THRESHOLD:
        return fail(f"overfit gap {overfit['gap']} not above threshold")
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    ctrl = doc.get("detector_control") or {}
    if ctrl.get("overfit_fired") is not True:
        return fail("receipt overfit_fired drift")
    if ctrl.get("honest_silent") is not True:
        return fail("receipt honest_silent drift")
    cands = {c["id"]: c for c in (doc.get("candidates") or []) if isinstance(c, dict)}
    rec_over = cands.get("fixture-overfit") or {}
    if rec_over.get("verdict") != "FAIL_GAMING":
        return fail("receipt overfit verdict drift")
    if rec_over.get("visible_score") is None or rec_over.get("holdout_score") is None:
        return fail("receipt did not report both scores")
    print(
        f"overfit_fired=True honest_silent=True "
        f"overfit_gap={overfit['gap']} threshold={C.GAP_THRESHOLD}"
    )
    print("SUCCESS:TST-0232-probe1 overfit gap detector fired; honest silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
