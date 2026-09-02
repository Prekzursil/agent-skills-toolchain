#!/usr/bin/env python3
"""Probe 1: detector control — known alias and known own-procedure first.

Both-states: live alias detection classifies the known alias as ALIAS; the
mutant with detect_alias=False classifies it as OWN-PROCEDURE (floor inflation).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import adapter as A  # noqa: E402
import corpus as C  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0048-adapter-slash-command.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0048-probe1 {msg}")
    return 1


def main() -> int:
    C.materialize()
    alias_path = C.CONTROLS / "known-alias.md"
    own_path = C.CONTROLS / "known-own-procedure.md"

    live_alias = A.classify(A.parse_file(alias_path, repo=REPO), detect_alias=True)
    live_own = A.classify(A.parse_file(own_path, repo=REPO), detect_alias=True)
    mutant_alias = A.classify(A.parse_file(alias_path, repo=REPO), detect_alias=False)

    print(
        "known-alias "
        f"verdict={live_alias.verdict} skill_id={live_alias.skill_id} "
        f"stages={len(live_alias.stages)} quote={live_alias.deciding_quote!r}"
    )
    print(
        "known-own-procedure "
        f"verdict={live_own.verdict} stages={len(live_own.stages)} "
        f"quote={live_own.deciding_quote!r}"
    )
    print(
        "mutant-detect_alias=false "
        f"verdict={mutant_alias.verdict} stages={len(mutant_alias.stages)}"
    )

    if live_alias.verdict != A.ALIAS:
        return fail(f"known alias classified {live_alias.verdict}")
    if live_alias.skill_id != "skill:docs":
        return fail(f"known alias skill_id={live_alias.skill_id}")
    if live_alias.stages:
        return fail("known alias must collapse to zero stages")
    if live_own.verdict != A.OWN_PROCEDURE:
        return fail(f"known own-procedure classified {live_own.verdict}")
    if len(live_own.stages) < 2:
        return fail(f"known own-procedure stage_count={len(live_own.stages)}")
    if mutant_alias.verdict != A.OWN_PROCEDURE:
        return fail("mutant must misclassify known alias as OWN-PROCEDURE")
    if mutant_alias.verdict == live_alias.verdict:
        return fail("both-states collapsed: mutant matched live")

    both_states = (
        live_alias.verdict == A.ALIAS
        and live_own.verdict == A.OWN_PROCEDURE
        and mutant_alias.verdict == A.OWN_PROCEDURE
    )
    print(f"both_states={both_states}")
    if not both_states:
        return fail("both-states control failed")

    ir = A.to_ir(live_own)
    if ir.get("runtime_entrypoint"):
        return fail("IR grew a runtime entrypoint")
    for st in ir["stages"]:
        if "line" not in st["source_anchor"]:
            return fail(f"stage {st['id']} missing source_anchor.line")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {st}")
        if "SUCCESS:WFA-0048" not in ART.read_text(encoding="utf-8"):
            return fail("sentinel absent")
        dc = doc.get("detector_control") or {}
        if not dc.get("pass"):
            return fail("artifact detector_control.pass is not true")

    print("SUCCESS:WFA-0048-probe1 detector-control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
