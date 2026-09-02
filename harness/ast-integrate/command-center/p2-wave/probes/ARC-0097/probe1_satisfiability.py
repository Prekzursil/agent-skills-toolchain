#!/usr/bin/env python3
"""Probe 1: every one of the 21 stopping conditions classified under PR-ONLY.

Consumer-side call site: loads the live contract (when present) and checks
the 21-row table, SC-13 as-written unsatisfiability, and both re-derivations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stopping as S  # noqa: E402

OUT = HERE / "probe1-satisfiability.raw.json"
ALLOWED = S.ALLOWED


def check_eval(ev: dict) -> list[str]:
    errs: list[str] = []
    rows = ev.get("stopping_conditions") or []
    if len(rows) != 21:
        errs.append(f"row-count={len(rows)} want=21")
    ids = [r.get("id") for r in rows]
    if ids != list(range(1, 22)):
        errs.append(f"ids={ids}")
    for r in rows:
        v = r.get("satisfiability_under_pr_only")
        if v not in ALLOWED:
            errs.append(f"sc{r.get('id')} verdict={v}")
    sc13 = next((r for r in rows if r.get("id") == 13), None)
    if not sc13:
        errs.append("sc13-missing")
    else:
        if sc13.get("satisfiability_under_pr_only") != "UNSATISFIABLE-AS-WRITTEN":
            errs.append("sc13-not-unsatisfiable-as-written")
        if "canary" not in str(sc13.get("text") or "").lower():
            errs.append("sc13-text-missing-canary")
    red = ev.get("unsatisfiability_rederivation") or {}
    if red.get("inherited_from_phase_graph") is not False:
        errs.append("inherited-from-phase-graph")
    if red.get("readings_agree") is not True:
        errs.append("readings-disagree")
    if red.get("verdict") != "UNSATISFIABLE-AS-WRITTEN":
        errs.append("rederive-verdict")
    t = red.get("reading_from_stopping_condition_text") or {}
    o = red.get("reading_from_owner_decision") or {}
    if not t or not o:
        errs.append("both-readings-absent")
    if not ev.get("ok"):
        errs.append("evaluate-ok-false")
    rm = ev.get("release_mode") or {}
    if str(rm.get("binding") or "") != "PR-ONLY":
        errs.append("release-mode")
    counts = ev.get("counts") or {}
    if sum(counts.get(k, 0) for k in ALLOWED) != 21:
        errs.append(f"counts={counts}")
    return errs


def check_contract(doc: dict, ev: dict) -> list[str]:
    errs: list[str] = []
    payload = S.contract_payload(doc)
    if doc.get("unit_id") != "ARC-0097":
        errs.append("contract-unit-id")
    if "SUCCESS:ARC-0097" not in json.dumps(doc):
        errs.append("contract-sentinel")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"contract-state={st}")
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(doc.get("report"), dict) and report.get("kind") != "contract-spec":
        errs.append("report-kind-not-contract-spec")
    rows = payload.get("stopping_conditions") or []
    if len(rows) != 21:
        errs.append(f"contract-rows={len(rows)}")
    live = {r["id"]: r["satisfiability_under_pr_only"] for r in ev["stopping_conditions"]}
    for r in rows:
        if not isinstance(r, dict):
            errs.append("contract-row-not-object")
            continue
        rid = r.get("id")
        if live.get(rid) != r.get("satisfiability_under_pr_only"):
            errs.append(f"contract-sc{rid}-mismatch")
        if r.get("satisfiability_under_pr_only") not in ALLOWED:
            errs.append(f"contract-sc{rid}-enum")
    handling = payload.get("sc13_handling") or {}
    if handling.get("as_written") != "UNSATISFIABLE-AS-WRITTEN":
        errs.append("contract-sc13-as-written")
    if handling.get("reinterpretation_forbidden") is not True:
        errs.append("contract-allows-reinterpretation")
    if handling.get("close_method") not in {
        "OWNER_EQUIVALENT_FORMULATION",
        "OWNER_WAIVER",
    }:
        errs.append("contract-sc13-close-method")
    if handling.get("owner_record_id") != "OQ-9":
        errs.append("contract-sc13-owner-id")
    red = payload.get("unsatisfiability_rederivation") or {}
    if red.get("inherited_from_phase_graph") is not False:
        errs.append("contract-inherited-phase-graph")
    if red.get("phase_graph_used_as_source") is True:
        errs.append("contract-used-phase-graph")
    if not red.get("reading_from_stopping_condition_text"):
        errs.append("contract-reading-text-absent")
    if not red.get("reading_from_owner_decision"):
        errs.append("contract-reading-owner-absent")
    return errs


def main() -> int:
    ev = S.evaluate()
    errs = check_eval(ev)
    doc = S.load_contract()
    contract_checked = False
    if doc is not None:
        contract_checked = True
        errs.extend(check_contract(doc, ev))
    payload = {
        "probe": "probe1-satisfiability",
        "unit_id": "ARC-0097",
        "counts": ev.get("counts"),
        "sc13": ev.get("sc13"),
        "readings_agree": ev["unsatisfiability_rederivation"]["readings_agree"],
        "inherited_from_phase_graph": False,
        "contract_present": contract_checked,
        "input_presence": ev.get("input_presence"),
        "errors": errs,
        "pass": not errs,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = ev["counts"]
    print(
        "conditions=21"
        f" SATISFIABLE={counts['SATISFIABLE']}"
        f" UNSATISFIABLE-AS-WRITTEN={counts['UNSATISFIABLE-AS-WRITTEN']}"
        f" NOT-CHECKED={counts['NOT-CHECKED']}"
        f" sc13={ev['sc13']['satisfiability_under_pr_only']}"
        f" readings_agree={ev['unsatisfiability_rederivation']['readings_agree']}"
        f" inherited_phase_graph=False"
        f" contract_checked={contract_checked}"
    )
    if errs:
        print("FAILED:ARC-0097-probe1 " + "; ".join(errs[:8]))
        return 1
    print("SUCCESS:ARC-0097-probe1 satisfiability check of 21 stopping conditions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
