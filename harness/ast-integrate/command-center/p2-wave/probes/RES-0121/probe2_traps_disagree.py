#!/usr/bin/env python3
"""Probe 2: named traps resolved; file-vs-classifier count; both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{G.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    art = G.REPO / G.OUT_REL
    if not art.is_file():
        return fail("artifact missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    rows = (doc.get("graph") or {}).get("rows") or []
    trap_problems = G.trap_checks(rows)
    if trap_problems:
        print(json.dumps(trap_problems))
        return fail(f"trap checks {trap_problems}")

    live_rows, _ = G.build_rows()
    live_problems = G.trap_checks(live_rows)
    if live_problems:
        return fail(f"live trap checks {live_problems}")

    disagree_art = G.disagreement_rows(rows)
    disagree_live = G.disagreement_rows(live_rows)
    if len(disagree_art) != len(disagree_live):
        return fail("disagreement count artifact vs live")
    recorded = (doc.get("counts") or {}).get("file_vs_classifier_disagreements")
    if recorded != len(disagree_art):
        return fail("counts.file_vs_classifier_disagreements drifted")
    if len(disagree_art) < 1:
        return fail("expected at least the BMAD NOASSERTION disagreement")

    healthy_ok, _ = G.graph_ok(rows)
    if not healthy_ok:
        return fail("healthy graph not ok")

    dropped = G.mutate_drop_sha256(rows, "TRAP-BMAD-METHOD")
    drop_ok, drop_problems = G.graph_ok(dropped)
    if drop_ok or "reachable-missing-sha256:TRAP-BMAD-METHOD" not in drop_problems:
        return fail(f"drop-sha256 silent {drop_problems}")

    hidden = G.mutate_hide_bmad_disagreement(rows)
    hide_problems = G.trap_checks(hidden)
    if "bmad-classifier-not-noassertion" not in hide_problems:
        return fail(f"hidden BMAD disagreement silent {hide_problems}")
    if "bmad-disagree-not-true" not in hide_problems:
        return fail(f"disagree flag plant silent {hide_problems}")

    verdicts = {v.get("id"): v for v in (doc.get("trap_verdicts") or [])}
    for name in ("BMAD-METHOD", "microsoft/autogen"):
        v = verdicts.get(name)
        if not v or v.get("resolved") is not True:
            return fail(f"trap_verdicts {name} unresolved")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "reachable-license-sha256",
        "named-traps-and-disagreement-control",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    out = {
        "probe": "probe2-traps-disagree",
        "unit_id": G.UNIT,
        "disagreements": len(disagree_art),
        "drop_sha256_fired": True,
        "hide_bmad_fired": True,
        "healthy_ok": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"disagreements={len(disagree_art)} drop_fired=True "
        f"hide_bmad_fired=True healthy_ok=True"
    )
    print(f"SUCCESS:{G.UNIT}-probe2 traps and disagreement both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
