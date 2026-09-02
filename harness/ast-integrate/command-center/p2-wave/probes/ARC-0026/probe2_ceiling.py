#!/usr/bin/env python3
"""Probe 2: ceiling curve, two-probe re-measure, overclaim, reviewer-added mode.

Mechanically different from probe 1: does not re-run the index/install
both-states tree. Re-runs the process probes today, checks the superlinear
detector against a plant, and requires REFUTED rows to name DESIGN vs SENTENCE.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import ceiling as C  # noqa: E402
import overclaim as O  # noqa: E402
import remeasure as R  # noqa: E402
import trees as T  # noqa: E402

ART = REPO / "command-center/phase3/A4/FAILURE-MODES.json"
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def main() -> int:
    T.ensure_fixtures()
    if not ART.is_file():
        print("FAILED:ARC-0026-probe2 FAILURE-MODES.json missing")
        return 1
    if DESIGN.is_file():
        print("FAILED:ARC-0026-probe2 A4 DESIGN.json present; this unit must not rebuild it")
        return 1

    ceil = C.run_ceiling()
    print(
        f"ceiling k={ceil['k_stdio_from_fixture_mcp']} "
        f"eager_sl={ceil['eager_superlinear']} plant_sl={ceil['planted_superlinear']} "
        f"eager={ceil['eager_stdio_curve']} plant={ceil['planted_superlinear_curve']}"
    )
    if not ceil.get("pass"):
        print("FAILED:ARC-0026-probe2 ceiling detector-control")
        return 1

    today = R.remeasure_today()
    print(
        f"ps_count={today['powershell_process_count']} "
        f"cfg_count={today['mcp_config_per_session_count']} "
        f"cited_estate_as_today={today['cited_estate_figure_as_today']} "
        f"engine={(today.get('powershell') or {}).get('engine')}"
    )
    if today.get("cited_estate_figure_as_today") is True:
        print("FAILED:ARC-0026-probe2 cited earlier estate figure as today")
        return 1
    if "combined_process_count" in today:
        print("FAILED:ARC-0026-probe2 combined process count present")
        return 1

    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0026-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0026-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0026-probe2 mutant without defect_locus was accepted")
        return 1

    live = doc.get("live_process_multiplication") or {}
    if int(live.get("powershell_process_count")) != int(today["powershell_process_count"]):
        # Process table can move during the same measure pass; require same
        # *config* derived count (stable) and that both fields exist as ints.
        print(
            "WARN:ARC-0026-probe2 process-table count moved "
            f"artifact={live.get('powershell_process_count')} live={today['powershell_process_count']}"
        )
    cfg_art = int(live["mcp_config_per_session_count"])
    cfg_now = int(today["mcp_config_per_session_count"])
    if cfg_art != cfg_now:
        print(f"FAILED:ARC-0026-probe2 mcp-config count drift art={cfg_art} now={cfg_now}")
        return 1
    if live.get("cited_estate_figure_as_today") is True:
        print("FAILED:ARC-0026-probe2 artifact cited estate figure as today")
        return 1

    ceil_doc = doc.get("ceiling_test") or {}
    if ceil_doc.get("eager_stdio_curve") != ceil["eager_stdio_curve"]:
        print("FAILED:ARC-0026-probe2 eager curve drift")
        return 1
    if ceil_doc.get("planted_superlinear") is not True:
        print("FAILED:ARC-0026-probe2 plant did not fire in artifact")
        return 1
    if ceil_doc.get("p1_on_eager") is True:
        print("FAILED:ARC-0026-probe2 P1 claimed on linear eager curve")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live_n = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0026-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live_n += 1
        else:
            print(f"FAILED:ARC-0026-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live_n < 1:
        print(f"FAILED:ARC-0026-probe2 evidence counts dossier={dossier} live={live_n}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0026-probe2 reviewer is not independent scope-only")
        return 1
    if rev.get("enumeration_certified_against_47") is True:
        print("FAILED:ARC-0026-probe2 cannot certify 47 classes; source file absent")
        return 1
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-PARTIAL-MATERIALIZE":
        print("FAILED:ARC-0026-probe2 reviewer did not add FM-PARTIAL-MATERIALIZE")
        return 1
    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    if "FM-PARTIAL-MATERIALIZE" in author_ids:
        print("FAILED:ARC-0026-probe2 added mode was already in the author list")
        return 1
    if added.get("caught_by_three_bit_signal") is True:
        print("FAILED:ARC-0026-probe2 partial-materialize must not be claimed caught")
        return 1

    if "SUCCESS:ARC-0026" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0026-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0026-probe2 ceiling remeasure overclaim reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
