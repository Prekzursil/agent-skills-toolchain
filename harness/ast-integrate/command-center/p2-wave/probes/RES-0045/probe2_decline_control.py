#!/usr/bin/env python3
"""Probe 2: defensible NO/DECLINE control + overclaim mutants.

Mechanically different from probe 1: does not print unique-id inventories.
Requires recommendation=DECLINE with a named lost capability, then drops a
rail / empties a unique list / flips to ADOPT / cites E3 as fact and requires
the checker to go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0045-probe2 artifact missing")
        return 1
    doc = C.load_art()
    errs = C.validate_decline_control(doc)
    m_rail = C.mutant_drop_rail_accepted(doc)
    m_list = C.mutant_drop_unique_list_accepted(doc)
    m_adopt = C.mutant_adopt_without_loss_accepted(doc)
    m_e3 = C.mutant_e3_cited_as_fact_accepted(doc)
    rec = doc.get("recommendation") or {}
    print(
        json.dumps(
            {
                "errors": errs,
                "verdict": rec.get("verdict"),
                "defensible_no": rec.get("defensible_no"),
                "lost": rec.get("capability_lost_if_declined"),
                "mutant_drop_rail_accepted": m_rail,
                "mutant_drop_unique_list_accepted": m_list,
                "mutant_adopt_accepted": m_adopt,
                "mutant_e3_cited_as_fact_accepted": m_e3,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if errs:
        print("FAILED:RES-0045-probe2 " + "; ".join(errs[:8]))
        return 1
    if m_rail:
        print("FAILED:RES-0045-probe2 mutant with one rail was accepted")
        return 1
    if m_list:
        print("FAILED:RES-0045-probe2 mutant empty unique-list was accepted")
        return 1
    if m_adopt:
        print("FAILED:RES-0045-probe2 mutant ADOPT without loss column was accepted")
        return 1
    if m_e3:
        print("FAILED:RES-0045-probe2 mutant E3-as-fact was accepted")
        return 1
    print(
        "SUCCESS:RES-0045-probe2 defensible-NO DECLINE "
        "mutants-rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
