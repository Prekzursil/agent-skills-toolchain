#!/usr/bin/env python3
"""Probe 2: counterfactual prevention — remove parent, does the child remain?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0110-root-cause-hierarchy-falsifiability.json"
SENTINEL = (
    "SUCCESS:ADV-0110 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0110 <reason>."
)
ALLOWED = set(E.ALLOWED)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0110-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0110-probe2 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:ADV-0110-probe2 not an object")
        return 1
    if doc.get("unit_id") != "ADV-0110":
        print("FAILED:ADV-0110-probe2 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0110-probe2 self-declared", st)
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0110-probe2 catalog sentinel absent")
        return 1

    live = E.investigate()
    control = live["control"]
    planted = live["planted"]
    # Independent of probe 1: re-run the hash-with vs hash-without experiment.
    with_eq = E.digest_with_parent(E.LF_PAYLOAD) == E.digest_with_parent(E.CRLF_PAYLOAD)
    without_eq = E.digest_without_parent(E.LF_PAYLOAD) == E.digest_without_parent(
        E.CRLF_PAYLOAD
    )
    if not (with_eq and not without_eq):
        print("FAILED:ADV-0110-probe2 CRLF control counterfactual did not fire")
        print(f"with_eq={with_eq} without_eq={without_eq}")
        return 1
    if not control["probe2_pass"]:
        print("FAILED:ADV-0110-probe2 genuine control probe2_pass=False")
        return 1
    if planted["probe2_pass"] or planted["removing_parent_prevents_child"]:
        print("FAILED:ADV-0110-probe2 planted label passed counterfactual")
        return 1
    if live["standin"]["n_probe2_fail"] != live["standin"]["n_edges"]:
        print(
            "FAILED:ADV-0110-probe2 expected every stand-in edge to fail counterfactual",
            live["standin"]["n_probe2_fail"],
            live["standin"]["n_edges"],
        )
        return 1
    if live["audit_sha256"] != doc.get("audit_sha256"):
        print("FAILED:ADV-0110-probe2 audit_sha256 drift")
        return 1
    art_targets = doc.get("enumerated_targets") or []
    live_by = {t["id"]: t["verdict"] for t in live["enumerated_targets"]}
    for row in art_targets:
        tid = row.get("id")
        v = row.get("verdict")
        if v not in ALLOWED or live_by.get(tid) != v:
            print("FAILED:ADV-0110-probe2 verdict", tid, v, live_by.get(tid))
            return 1
    payload = {
        "probe": "probe2-counterfactual-prevention",
        "unit_id": "ADV-0110",
        "pass": True,
        "audit_sha256": live["audit_sha256"],
        "control_with_parent_equal": with_eq,
        "control_without_parent_equal": without_eq,
        "removing_parent_prevents_child": True,
        "planted_prevents_child": False,
        "standin_counterfactual_fail": live["standin"]["n_probe2_fail"],
        "standin_edges": live["standin"]["n_edges"],
        "syn0001_present": live["syn0001"]["present"],
        "overall_verdict": live["overall_verdict"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"crlf_with={with_eq} crlf_without={without_eq} "
        f"standin_fail={payload['standin_counterfactual_fail']}/{payload['standin_edges']}"
    )
    print("SUCCESS:ADV-0110-probe2 counterfactual prevention re-derived and matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
