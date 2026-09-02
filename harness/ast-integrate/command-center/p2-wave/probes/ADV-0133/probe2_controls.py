#!/usr/bin/env python3
"""Probe 2: CONFIRMED premise empty closure + structural join completeness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from corpus import CONFIRMED_PREMISE_ID, OUT_REL, UNIT_ID, WORKED_PREMISE_ID  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0133-probe2 {msg}")
    return 1


def main() -> int:
    report = E.build_report(REPO)
    controls = report.get("confirmed_controls") or []
    if not controls:
        return fail("no CONFIRMED control recorded")
    for row in controls:
        if row.get("status") != "CONFIRMED":
            return fail(f"{row.get('premise_id')} status={row.get('status')}")
        union_size = row.get("union_size")
        if union_size is None or int(union_size) != 0:
            return fail(
                f"{row.get('premise_id')} union_size={union_size} "
                "(detector matched text, not status)"
            )
        if row.get("union"):
            return fail(f"{row.get('premise_id')} non-empty union {row.get('union')[:8]}")

    completeness = report.get("join_completeness") or {}
    if completeness.get("worked_premise_id") != WORKED_PREMISE_ID:
        return fail("join_completeness not on the worked case")
    if completeness.get("shrunk") is not True:
        return fail(
            f"structural join inert full={completeness.get('full_union_size')} "
            f"cut={completeness.get('without_structural_size')}"
        )
    if completeness.get("structural_join_inert") is True:
        return fail("structural_join_inert true after shrink")
    extra = completeness.get("structural_only_members") or []
    if not extra:
        return fail("no structural-only members; shrink cannot be attributed")

    out = REPO / OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(out.read_text(encoding="utf-8"))
    payload = E.artifact_payload(doc)
    art_c = payload.get("confirmed_controls") or []
    art_union_size = None if not art_c else art_c[0].get("union_size")
    if art_union_size is None or int(art_union_size) != 0:
        return fail("artifact CONFIRMED control not empty")
    art_j = payload.get("join_completeness") or {}
    if art_j.get("shrunk") is not True:
        return fail("artifact join_completeness.shrunk is not true")
    if int(art_j.get("full_union_size") or 0) <= int(art_j.get("without_structural_size") or 0):
        return fail("artifact structural join did not shrink")
    if int(completeness["full_union_size"]) <= int(completeness["without_structural_size"]):
        return fail("live structural join did not shrink")

    # Independent rebuild: live engine vs artifact member ids.
    live_ids = set()
    for c in report["closures"]:
        if c.get("premise_id") == WORKED_PREMISE_ID:
            live_ids = {
                m
                for m in (c.get("union") or [])
                if m.startswith("unit:")
                or m in {"17-DECISION-LOG.md", "pinned-program-brief", "command-center/WORK-UNIT-CATALOG.json"}
            }
    art_ids = set()
    for c in payload.get("closures") or []:
        if c.get("premise_id") == WORKED_PREMISE_ID:
            art_ids = {
                m
                for m in (c.get("union") or [])
                if m.startswith("unit:")
                or m in {"17-DECISION-LOG.md", "pinned-program-brief", "command-center/WORK-UNIT-CATALOG.json"}
            }
    if live_ids != art_ids:
        return fail(
            f"independent rebuild disagrees only_live={sorted(live_ids-art_ids)[:8]} "
            f"only_art={sorted(art_ids-live_ids)[:8]}"
        )

    payload = {
        "pass": True,
        "probe": "probe2-controls",
        "unit_id": UNIT_ID,
        "confirmed_premise_id": CONFIRMED_PREMISE_ID,
        "confirmed_union_size": 0,
        "full_union_size": completeness["full_union_size"],
        "without_structural_size": completeness["without_structural_size"],
        "structural_only": len(extra),
        "reviewer_id": "ADV-0133-probe2-independent-rebuild",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:ADV-0133-probe2 CONFIRMED closure empty; "
        "structural join shrinks "
        f"{completeness['full_union_size']}->{completeness['without_structural_size']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
