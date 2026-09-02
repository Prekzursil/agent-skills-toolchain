#!/usr/bin/env python3
"""Probe 1: known-present USE must fire; known-absent MENTION must not.

The two controls share the same implementer-conclusion needle so a TEXT
matcher cannot distinguish them. ROLE classification is the signal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_corpus, write_corpus  # noqa: E402
from detector import cite, detect_item, evaluate  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0131.json"


def main() -> int:
    write_corpus()
    corpus = load_corpus()
    needles = corpus["needles"]
    by_id = {t["id"]: t for t in corpus["transcripts"]}
    present = by_id["use-01"]
    absent = by_id["mention-01"]
    if present["needle"] != absent["needle"]:
        print("FAILED:CNF-0131-probe1 controls do not share a needle")
        return 1
    p = detect_item(present, needles)
    a = detect_item(absent, needles)
    print(
        json.dumps(
            {
                "probe": "probe1-known-present-absent",
                "unit_id": "CNF-0131",
                "shared_needle_id": present["needle_id"],
                "cite": cite(),
                "known_present": p,
                "known_absent": a,
                "text_only_would_fire_on_mention": a["text_only_fired"],
            },
            sort_keys=True,
        )
    )
    if not p["fired"]:
        print("FAILED:CNF-0131-probe1 known-present did not fire")
        return 1
    if a["fired"]:
        print("FAILED:CNF-0131-probe1 known-absent fired (use-vs-mention miss)")
        return 1
    if not a["text_only_fired"]:
        print("FAILED:CNF-0131-probe1 mention lacks needle text; control is vacuous")
        return 1
    if p["role"] != "USE" or a["role"] != "MENTION":
        print(f"FAILED:CNF-0131-probe1 roles present={p['role']} absent={a['role']}")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0131-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0131-probe1 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0131" not in text:
        print("FAILED:CNF-0131-probe1 sentinel absent")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    kp = tests.get("known-present") or {}
    ka = tests.get("known-absent") or {}
    if kp.get("result") != "PASS" or ka.get("result") != "PASS":
        print("FAILED:CNF-0131-probe1 receipt tests not PASS")
        return 1
    ev = evaluate(corpus)
    if not ev["pass"]:
        print("FAILED:CNF-0131-probe1 live evaluate failed")
        return 1
    print("SUCCESS:CNF-0131-probe1 known-present fires, known-absent silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
