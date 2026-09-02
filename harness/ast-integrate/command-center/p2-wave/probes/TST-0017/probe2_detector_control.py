#!/usr/bin/env python3
"""Probe 2: detector control — naive substring USE vs wrapped-context MENTION.

Does not trust the receipt's conclusion. Re-runs both states:
  * known-good: the kit classifies fenced/docs FAILED as MENTION
  * known-broken: ignore_wrappers (and naive substring) classifies the same
    spans as USE
A detector silent in both states is disqualified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import kit  # noqa: E402

ART = REPO / "command-center/receipts/TST-0017.json"
FENCED = HERE / "fixtures" / "fenced.md"
KIT_DOC = HERE / "KIT.md"
TYPED = HERE / "fixtures" / "typed_status.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0017-probe2 {msg}")
    return 1


def main() -> int:
    fenced = FENCED.read_text(encoding="utf-8")
    docs = KIT_DOC.read_text(encoding="utf-8")
    typed = TYPED.read_text(encoding="utf-8")

    good_fenced = kit.roles(fenced, "FAILED")
    broken_fenced = kit.roles(fenced, "FAILED", ignore_wrappers=True)
    naive_fenced = [o.role for o in kit.naive_substring_as_use(fenced, "FAILED")]
    good_docs = kit.roles(docs, "FAILED")
    broken_docs = kit.roles(docs, "FAILED", ignore_wrappers=True)
    good_typed = kit.roles(typed, "FAILED")
    broken_typed = kit.roles(typed, "FAILED", ignore_wrappers=True)

    checks = [
        ("fenced-good-all-mention", bool(good_fenced) and set(good_fenced) == {"MENTION"}),
        ("fenced-broken-all-use", bool(broken_fenced) and set(broken_fenced) == {"USE"}),
        ("fenced-naive-all-use", bool(naive_fenced) and set(naive_fenced) == {"USE"}),
        ("fenced-both-states-differ", good_fenced != broken_fenced),
        ("docs-good-all-mention", bool(good_docs) and set(good_docs) == {"MENTION"}),
        ("docs-broken-all-use", bool(broken_docs) and set(broken_docs) == {"USE"}),
        ("typed-good-use", good_typed == ["USE"]),
        ("typed-broken-still-use", broken_typed == ["USE"]),
        (
            "silent-in-both-states-rejected",
            good_fenced != broken_fenced and set(good_fenced) == {"MENTION"},
        ),
    ]
    summary = {name: ok for name, ok in checks}
    print(json.dumps({"probe": "probe2-detector-control", **summary}, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            return fail(name)

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0017" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    dc = doc.get("detector_control") or {}
    if dc.get("silent_on_known_good") is not True:
        return fail("artifact silent_on_known_good not true")
    if dc.get("fires_on_known_broken") is not True:
        return fail("artifact fires_on_known_broken not true")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") not in {"PASS", "PASS"}:
        # accept PASS (schema) 
        if reviewer.get("verdict") != "PASS":
            return fail("reviewer verdict not PASS")
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    print("SUCCESS:TST-0017-probe2 detector-control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
