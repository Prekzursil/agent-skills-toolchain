#!/usr/bin/env python3
"""Probe 1: however-only conclusion is UNCHALLENGED (use-versus-mention).

The estate trap is classifying a hedge word as if a disconfirming search
had been run. The mention-trap mutant must CHALLENGE the same object; the
live classifier must not. A detector that is silent on both the trap and
the real rule, or that fires on both, is broken.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import (  # noqa: E402
    CHALLENGED,
    UNCHALLENGED,
    classify,
    mention_trap_classify,
)
from contract import OUT_REL, SENTINEL, UNIT  # noqa: E402
from controls import HOWEVER_ONLY  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def independent_however_check(conclusion: dict) -> str:
    """Second implementation: only the structured triple counts.

    Does not import classify.extract_record. Looks at the known record keys
    and requires query + list result_set + verdict. Does not grep 'however'.
    """
    rec = conclusion.get("counterevidence_search")
    if not isinstance(rec, dict):
        rec = conclusion.get("disconfirming_search")
    if not isinstance(rec, dict):
        rec = conclusion.get("challenge_record")
    if not isinstance(rec, dict):
        return UNCHALLENGED
    query = rec.get("query")
    results = rec.get("result_set")
    verdict = rec.get("verdict")
    if isinstance(query, str) and query.strip() and isinstance(results, list) and isinstance(verdict, str) and verdict.strip():
        return CHALLENGED
    return UNCHALLENGED


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact-missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text and f"SUCCESS:{UNIT}" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail("unit_id")

    live = classify(HOWEVER_ONLY)
    indie = independent_however_check(HOWEVER_ONLY)
    trap = mention_trap_classify(HOWEVER_ONLY)
    print(
        f"however_only live={live['status']} indie={indie} "
        f"mention_trap={trap['status']} reason={live['reason']}"
    )
    if live["status"] != UNCHALLENGED:
        return fail(f"live-classified-however-as-{live['status']}")
    if indie != UNCHALLENGED:
        return fail(f"indie-classified-however-as-{indie}")
    if trap["status"] != CHALLENGED:
        return fail("mention-trap-did-not-fire; control is uninformative")

    # A copy that still only mentions however, plus a fake caveat field.
    mutant = copy.deepcopy(HOWEVER_ONLY)
    mutant["strongest_surviving_counterargument"] = "however the sample is small"
    if classify(mutant)["status"] != UNCHALLENGED:
        return fail("caveat-field-promoted-to-challenge")

    controls = doc.get("controls") or {}
    however_row = None
    for row in controls.get("labeled") or []:
        if row.get("id") == HOWEVER_ONLY["id"]:
            however_row = row
            break
    if not however_row:
        return fail("artifact-omitted-however-control")
    if however_row.get("status") != UNCHALLENGED:
        return fail(f"artifact-however-status={however_row.get('status')}")

    rule = str(doc.get("challenge_rule") or "")
    if "however" not in rule.lower() or "does not count" not in rule.lower():
        return fail("artifact-did-not-state-hedge-rule")

    tests = doc.get("tests") or []
    hit = False
    for t in tests:
        if t.get("id") == "however-only-unchallenged":
            hit = True
            if t.get("pass") is not True:
                return fail("artifact-test-not-pass")
            if t.get("observed_status") != UNCHALLENGED:
                return fail("artifact-test-observed-drift")
    if not hit:
        return fail("artifact-missing-however-test")

    summary = {
        "probe": "probe1-however-negative-control",
        "unit_id": UNIT,
        "however_status": UNCHALLENGED,
        "mention_trap_status": CHALLENGED,
        "two_implementations_agree": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe1 however-only UNCHALLENGED mention-trap CHALLENGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
