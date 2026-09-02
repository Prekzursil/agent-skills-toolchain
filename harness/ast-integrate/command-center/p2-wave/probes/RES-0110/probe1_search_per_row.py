#!/usr/bin/env python3
"""Probe 1: every row has a live re-run implementation-search; control is found."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    CONTROL_MECH_ID,
    CONTROL_KNOWN_IMPL,
    OUTPUT_REL,
    QUESTION,
    REPO,
    SENTINEL,
    UNIT_ID,
)
import schema_local as SL  # noqa: E402
from search import detector_control, load_index, search_mechanism  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    path = REPO / OUTPUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return fail("artifact missing")
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    body = SL.payload(doc)
    if body.get("question") != QUESTION:
        return fail("question-mismatch")
    try:
        SL.assert_valid(doc)
        SL.assert_rejects_garbage()
    except ValueError as exc:
        return fail(str(exc).split("\n", 1)[0])

    rows = list((body.get("register") or {}).get("rows") or [])
    if len(rows) < 3:
        return fail(f"register too small n={len(rows)}")
    idx = load_index()
    for row in rows:
        rid = row.get("id")
        search = row.get("implementation_search") or {}
        if search.get("performed") is not True:
            return fail(f"{rid} implementation-search not performed")
        if not search.get("queries"):
            return fail(f"{rid} search queries missing")
        live = search_mechanism(rid, idx)
        if live["verdict"] != search.get("verdict"):
            return fail(
                f"{rid} artifact verdict {search.get('verdict')} != live {live['verdict']}"
            )
        if live["performed"] is not True:
            return fail(f"{rid} live search not performed")
        print(f"row {rid} search={live['verdict']} hits={live['hit_count']} popular={live['popular_hit_count']}")

    det = detector_control(idx)
    print(
        f"detector found_known={det['found_known']} "
        f"silent_on_absent={det['silent_on_absent']} passed={det['passed']}"
    )
    if not det["passed"]:
        return fail("detector control failed on re-run")
    ctrl = next((r for r in rows if r.get("id") == CONTROL_MECH_ID), None)
    if ctrl is None:
        return fail("control row missing")
    names = " ".join(
        str(h.get("name") or "")
        for h in (ctrl.get("implementation_search") or {}).get("hits") or []
    )
    if CONTROL_KNOWN_IMPL not in names:
        return fail("control row did not record the known implementation")
    if (ctrl.get("promotion") or {}).get("is_gem"):
        return fail("control row promoted as gem")
    gems = [r for r in rows if (r.get("promotion") or {}).get("is_gem")]
    if not gems:
        return fail("no promoted gems")
    for g in gems:
        paper = g.get("paper") or {}
        if paper.get("effect_size") is None or paper.get("baseline") is None:
            return fail(f"gem {g.get('id')} missing effect or baseline")
        if (g.get("implementation_search") or {}).get("verdict") != "no-popular-implementation":
            return fail(f"gem {g.get('id')} search verdict")
    print(f"gems={[g['id'] for g in gems]} control={CONTROL_MECH_ID}")
    print(f"SUCCESS:{UNIT_ID}-probe1 search-per-row detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
