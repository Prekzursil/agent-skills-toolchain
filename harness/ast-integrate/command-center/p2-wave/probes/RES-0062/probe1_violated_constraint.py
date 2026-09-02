#!/usr/bin/env python3
"""Probe 1: name the determinism constraint an LLM step violates, cited to an engine rule."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanics as m  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0062-probe1 {msg}")
    return 1


def main() -> int:
    snap = m.verify_snapshots()
    if not snap["pass"]:
        return fail(f"snapshots bad={snap['bad']} quotes={snap['missing_quotes']}")
    live = m.build_record()
    graded = m.grade_artifact(live)
    if not graded["pass"]:
        return fail(f"live-grade {graded['reasons']}")
    mutant = m.mutant_partial_replay(live)
    bad = m.grade_artifact(mutant)
    if bad["pass"]:
        return fail("partial-replay mutant was silent")
    if "constraint-id-missing" not in bad["reasons"]:
        return fail(f"mutant reasons {bad['reasons']}")
    if "did-not-reject-partial" not in bad["reasons"]:
        return fail(f"mutant did not trip partial reject {bad['reasons']}")

    art_path = m.REPO / m.ART_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    art_grade = m.grade_artifact(doc)
    if not art_grade["pass"]:
        return fail(f"artifact-grade {art_grade['reasons']}")
    vc = doc["answer"]["violated_constraint"]
    if vc.get("id") != m.CONSTRAINT_ID:
        return fail("artifact constraint id")
    rule = vc.get("engine_rule") or ""
    if "same sequence of Commands" not in rule:
        return fail("engine rule missing Temporal command-sequence clause")
    if "ctx.run" not in rule:
        return fail("engine rule missing Restate ctx.run")
    if "same steps" not in rule:
        return fail("engine rule missing DBOS step-order clause")
    claims = {c["id"]: c for c in doc["claims"]}
    llm = claims["C-TEMPORAL-LLM-MUST-BE-ACTIVITY"]
    if llm.get("evidence_tier") not in {"E1", "E2"}:
        return fail(f"LLM-activity claim tier {llm.get('evidence_tier')}")
    kinds = {r["kind"] for r in llm["rails"]}
    if "prose" not in kinds or "api" not in kinds:
        return fail(f"LLM-activity rails not dual-kind {kinds}")
    brk = claims["C-LLM-BREAKS-COMMAND-IDENTITY"]
    if brk.get("evidence_tier") in {"E3", "E4"}:
        return fail("break-identity claim is single-rail")
    report = {
        "probe": "probe1-violated-constraint",
        "unit_id": m.UNIT,
        "constraint_id": m.CONSTRAINT_ID,
        "mutant_reasons": bad["reasons"],
        "live_pass": True,
        "artifact_pass": True,
        "llm_activity_tier": llm.get("evidence_tier"),
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:RES-0062-probe1 named violated constraint cited to engine rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
