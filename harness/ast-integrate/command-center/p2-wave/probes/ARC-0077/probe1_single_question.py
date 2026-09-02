#!/usr/bin/env python3
"""Probe 1: single-question assertion + four-item checklist on the packet.

Live packet must ask exactly one foundation-level decision. A mutant with a
second prompt must fail the same checker (both-states). Checklist items are
recomputed from the packet fields, not trusted from stored booleans.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import packet as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0077-probe1 {msg}")
    return 1


def main() -> int:
    path = REPO / P.PACKET_REL
    if not path.is_file():
        return fail(f"packet-absent {P.PACKET_REL}")
    doc = P.load_packet(REPO)
    n = P.count_decision_prompts(doc)
    print(f"decision_prompts={n}")
    if n != 1:
        return fail(f"expected-1-got-{n}")
    ok, items = P.checklist_pass(doc)
    for row in items:
        print(f"checklist {row['id']} ok={row['ok']} rule={row['rule']}")
    if not ok:
        return fail("checklist-live-fail")
    stored = doc.get("owner_interaction_checklist")
    if isinstance(stored, list) and stored:
        stored_ok = {str(r.get("id")): bool(r.get("ok")) for r in stored if isinstance(r, dict)}
        live_ok = {r["id"]: bool(r["ok"]) for r in items}
        if stored_ok != live_ok:
            return fail(f"stored-checklist-drift stored={stored_ok} live={live_ok}")
    mutant = P.mutant_second_question(doc)
    m_ok, m_items = P.checklist_pass(mutant)
    m_n = P.count_decision_prompts(mutant)
    print(f"mutant_prompts={m_n} mutant_checklist_ok={m_ok}")
    if m_n != 2:
        return fail(f"mutant-should-have-2-got-{m_n}")
    if m_ok:
        return fail("mutant-second-question-did-not-fire")
    one_q = next(r for r in m_items if r["id"] == "one_foundation_question")
    if one_q["ok"]:
        return fail("mutant-one-question-item-still-true")
    text = path.read_text(encoding="utf-8")
    if text.count('"kind": "foundation"') < 1:
        return fail("foundation-kind-absent-from-bytes")
    print("single_question=True four_item=True mutant_fired=True")
    print("SUCCESS:ARC-0077-probe1 single-question checklist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
