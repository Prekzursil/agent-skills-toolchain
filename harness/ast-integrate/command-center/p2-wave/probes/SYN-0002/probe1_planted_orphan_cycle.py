#!/usr/bin/env python3
"""Probe 1: planted-orphan and planted-cycle FIRE; clean is SILENT.

Prints the four counts with denominators and the gate exit code on both
the planted-defect fixtures and the clean graph. A live zero without a
planted run is rejected; a missing live SYN-0001 graph is NOT-CHECKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gate import format_counts, run_paths  # noqa: E402
from paths import (  # noqa: E402
    CLAIMS_CLEAN,
    CLAIMS_ORPHAN,
    COMPLETION_SENTINEL,
    GRAPH_CLEAN,
    GRAPH_CYCLE,
    LIVE_CLAIMS,
    LIVE_GRAPH,
    LIVE_RISKS,
    LIVE_UNKNOWNS,
    OUT,
    REPO,
    RISKS,
    UNKNOWNS,
)


def dump(name: str, result) -> None:
    print(f"[{name}] observed={result.observed} exit_code={result.exit_code}")
    if result.input_error:
        print(f"[{name}] input_error={result.input_error}")
    for line in format_counts(result.counts):
        print(f"[{name}] {line}")
    for finding in result.findings[:8]:
        print(f"[{name}] FINDING {finding.code} {finding.subject}")


def main() -> int:
    orphan = run_paths(GRAPH_CLEAN, CLAIMS_ORPHAN, RISKS, UNKNOWNS)
    cycle = run_paths(GRAPH_CYCLE, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    clean = run_paths(GRAPH_CLEAN, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    dump("planted_orphan", orphan)
    dump("planted_cycle", cycle)
    dump("clean", clean)

    if orphan.observed != "FIRED" or orphan.exit_code == 0:
        print("FAILED:SYN-0002-probe1 planted orphan did not FIRE")
        return 1
    if "orphaned-finding" not in {f.code for f in orphan.findings}:
        print("FAILED:SYN-0002-probe1 planted orphan missing orphaned-finding code")
        return 1
    if cycle.observed != "FIRED" or cycle.exit_code == 0:
        print("FAILED:SYN-0002-probe1 planted cycle did not FIRE")
        return 1
    if "cycle-in-causal-graph" not in {f.code for f in cycle.findings}:
        print("FAILED:SYN-0002-probe1 planted cycle missing cycle code")
        return 1
    if clean.observed != "SILENT" or clean.exit_code != 0 or clean.findings:
        print("FAILED:SYN-0002-probe1 clean graph was not SILENT")
        return 1
    oc = clean.counts["orphan_claims"]
    print(
        f"clean_orphan_claims={oc['numerator']}/{oc['denominator']} "
        "exit=0 (zero-orphan trusted only because planted-orphan FIRED)"
    )

    live_graph = REPO / LIVE_GRAPH
    live_claims = REPO / LIVE_CLAIMS
    if not live_graph.is_file() or not live_claims.is_file():
        print(
            "live_status=NOT-CHECKED "
            f"graph_present={live_graph.is_file()} claims_present={live_claims.is_file()} "
            "(missing live SYN-0001/CLAIM-REGISTRY is not a zero-orphan pass)"
        )
        live_status = "NOT-CHECKED"
    else:
        live = run_paths(
            live_graph,
            live_claims,
            REPO / LIVE_RISKS if (REPO / LIVE_RISKS).is_file() else None,
            REPO / LIVE_UNKNOWNS if (REPO / LIVE_UNKNOWNS).is_file() else None,
        )
        dump("live", live)
        live_status = live.observed

    art = REPO / OUT
    if not art.is_file():
        print("FAILED:SYN-0002-probe1 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if COMPLETION_SENTINEL not in text:
        print("FAILED:SYN-0002-probe1 completion sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:SYN-0002-probe1 self-declared {doc.get('state')}")
        return 1
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    control_list = report.get("controls") or doc.get("controls") or []
    controls = {c["id"]: c for c in control_list if isinstance(c, dict)}
    for cid, want in (
        ("planted-orphan", "FIRED"),
        ("planted-cycle", "FIRED"),
        ("clean", "SILENT"),
    ):
        row = controls.get(cid) or {}
        if row.get("observed") != want:
            print(f"FAILED:SYN-0002-probe1 receipt {cid} observed={row.get('observed')} want={want}")
            return 1
    live_doc = report.get("live") if isinstance(report.get("live"), dict) else doc.get("live") or {}
    if live_status == "NOT-CHECKED" and str(live_doc.get("status") or "") == "SILENT":
        print("FAILED:SYN-0002-probe1 receipt claims live SILENT while inputs are absent")
        return 1
    print("SUCCESS:SYN-0002-probe1 detector-control planted-orphan+cycle FIRED clean SILENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
