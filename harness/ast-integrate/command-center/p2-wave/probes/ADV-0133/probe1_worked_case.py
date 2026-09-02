#!/usr/bin/env python3
"""Probe 1: M-NN worked case reaches beyond its source document."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from corpus import (  # noqa: E402
    OUT_REL,
    PINNED_BRIEF,
    SENTINEL,
    SOURCE_DOC,
    STATUSES,
    UNIT_ID,
    WORKED_PREMISE_ID,
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0133-probe1 {msg}")
    return 1


def main() -> int:
    report = E.build_report(REPO)
    closures = [c for c in report["closures"] if c.get("premise_id") == WORKED_PREMISE_ID]
    if len(closures) != 1:
        return fail(f"expected 1 worked closure, got {len(closures)}")
    live = closures[0]
    union = set(live.get("union") or [])
    members = live.get("members") or []
    if SOURCE_DOC not in union:
        return fail("17-DECISION-LOG.md missing from closure")
    if PINNED_BRIEF not in union:
        return fail("pinned program brief missing from closure")
    downstream = [m for m in union if m.startswith("unit:")]
    if not downstream:
        return fail("no downstream unit briefs in closure (one-directional read)")
    if union <= {SOURCE_DOC}:
        return fail("closure is source-document-only")
    unmarked = [m["id"] for m in members if m.get("status") not in STATUSES]
    if unmarked:
        return fail(f"unmarked members {unmarked[:8]}")
    joins = live.get("three_joins") or {}
    for name in ("textual", "temporal", "structural"):
        if name not in joins or not isinstance(joins[name], list):
            return fail(f"missing join {name}")
    if not joins["textual"]:
        return fail("textual join empty on worked case")
    if not joins["structural"]:
        return fail("structural join empty on worked case")

    out = REPO / OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(out.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    payload = E.artifact_payload(doc)
    art = None
    for row in payload.get("closures") or []:
        if row.get("premise_id") == WORKED_PREMISE_ID:
            art = row
            break
    if art is None:
        return fail("artifact missing worked closure")
    art_union = set(art.get("union") or [])
    core = {SOURCE_DOC, PINNED_BRIEF}
    live_core = {m for m in union if m.startswith("unit:") or m in core or m == "command-center/WORK-UNIT-CATALOG.json"}
    art_core = {m for m in art_union if m.startswith("unit:") or m in core or m == "command-center/WORK-UNIT-CATALOG.json"}
    if live_core != art_core:
        return fail(
            f"catalog-derived union drifted only_live={sorted(live_core-art_core)[:8]} "
            f"only_art={sorted(art_core-live_core)[:8]}"
        )
    missing_art_files = [
        m for m in art_union
        if m not in union and not m.startswith("unit:") and m not in core
    ]
    if missing_art_files:
        return fail(f"artifact file members missing from live {missing_art_files[:8]}")
    wc = payload.get("worked_case") or {}
    if wc.get("reaches_beyond_source") is not True:
        return fail("worked_case.reaches_beyond_source is not true")
    if wc.get("missing_required_members"):
        return fail(f"missing required {wc.get('missing_required_members')}")

    payload = {
        "pass": True,
        "probe": "probe1-worked-case",
        "unit_id": UNIT_ID,
        "union_size": len(union),
        "downstream_unit_briefs": len(downstream),
        "source_document": SOURCE_DOC,
        "pinned_brief": PINNED_BRIEF,
        "reaches_beyond_source": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:ADV-0133-probe1 worked M-NN closure includes source, "
        f"pinned brief, and {len(downstream)} downstream unit briefs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
