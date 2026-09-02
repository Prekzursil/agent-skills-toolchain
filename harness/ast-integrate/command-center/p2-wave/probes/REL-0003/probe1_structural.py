#!/usr/bin/env python3
"""Probe 1: structural one-question check, spec quote, PHASE-GRAPH citation, anti-re-ask.

Mechanically different from probe 2: reads OWNER-DECISIONS.md and PHASE-GRAPH.json
and counts interrogatives. Does not perform catalog id lookup.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import validator as V  # noqa: E402

ART = REPO / "command-center/receipts/REL-0003.json"
OWNER = REPO / "command-center/OWNER-DECISIONS.md"
PHASE = REPO / "command-center/PHASE-GRAPH.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:REL-0003-probe1 packet missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:REL-0003" not in text:
        print("FAILED:REL-0003-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:REL-0003-probe1 self-declared {doc.get('state')}")
        return 1

    nq = V.question_count(doc)
    print(f"question_count={nq}")
    if nq != 1:
        print("FAILED:REL-0003-probe1 packet is not exactly one question")
        return 1

    two_q = copy.deepcopy(doc)
    two_q["question"] = str(doc["question"]) + " Should we also waive condition 12?"
    two_n = V.question_count(two_q)
    two_schema = V.schema_errors(two_q)
    print(f"second_question_count={two_n} schema_errors={len(two_schema)}")
    if two_n == 1 or not two_schema:
        print("FAILED:REL-0003-probe1 second question did not fail the check")
        return 1

    quote_errs = V.spec_quote_errors(doc)
    print(f"spec_quote_11390 verbatim={doc.get('spec_quote_11390', {}).get('verbatim')!r}")
    if quote_errs:
        print("FAILED:REL-0003-probe1 spec quote")
        for e in quote_errs:
            print(" ", e)
        return 1

    if not PHASE.is_file():
        print("FAILED:REL-0003-probe1 PHASE-GRAPH.json missing")
        return 1
    phase = json.loads(PHASE.read_text(encoding="utf-8"))
    pg_errs = V.phase_graph_errors(doc, phase)
    needed = (phase.get("constrained_by_release_mode") or {}).get("owner_decision_needed")
    print(f"phase_graph_field=constrained_by_release_mode.owner_decision_needed value={needed}")
    if pg_errs:
        print("FAILED:REL-0003-probe1 PHASE-GRAPH citation")
        for e in pg_errs:
            print(" ", e)
        return 1

    if not OWNER.is_file():
        print("FAILED:REL-0003-probe1 OWNER-DECISIONS.md missing")
        return 1
    owner_text = OWNER.read_text(encoding="utf-8")
    anti = V.anti_reask_errors(doc, owner_text)
    print(f"anti_reask_live_errors={len(anti)}")
    if anti:
        print("FAILED:REL-0003-probe1 live packet re-asks a settled decision")
        for e in anti:
            print(" ", e)
        return 1

    reask = copy.deepcopy(doc)
    reask["question"] = (
        "Prompt Two — release mode: PR-ONLY / PRIVATE CANARY / PUBLIC MARKETPLACE?"
    )
    reask_errs = V.anti_reask_errors(reask, owner_text)
    print(f"anti_reask_control_errors={len(reask_errs)}")
    if not reask_errs:
        print("FAILED:REL-0003-probe1 re-ask of OQ-3 was not caught")
        return 1

    loc = doc.get("durable_record_location") or {}
    line = loc.get("line")
    lines = owner_text.splitlines()
    if not isinstance(line, int) or line < 1 or line > len(lines):
        print("FAILED:REL-0003-probe1 durable record line out of range")
        return 1
    window = "\n".join(lines[max(0, line - 3) : line + 5])
    if "REL-0003" not in window or "answer:" not in window:
        print("FAILED:REL-0003-probe1 receipt does not cite OWNER-DECISIONS.md file:line")
        return 1
    print(f"durable_record={loc.get('path')}:{line}")
    print("SUCCESS:REL-0003-probe1 structural one-question spec-quote anti-reask")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
