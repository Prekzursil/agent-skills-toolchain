#!/usr/bin/env python3
"""Probe 1: per-link refuting observation vs evidence channel (falsifiability)."""
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
        print("FAILED:ADV-0110-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0110-probe1 unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:ADV-0110-probe1 not an object")
        return 1
    if doc.get("unit_id") != "ADV-0110":
        print("FAILED:ADV-0110-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0110-probe1 self-declared", st)
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0110-probe1 catalog sentinel absent")
        return 1

    live = E.investigate()
    control = live["control"]
    planted = live["planted"]
    if not control["probe1_pass"] or control["probe1"] != "FALSIFIABLE":
        print("FAILED:ADV-0110-probe1 genuine control is not falsifiable")
        return 1
    if planted["probe1"] != "LABEL" or planted["refuting_observation"] is not None:
        print("FAILED:ADV-0110-probe1 planted label did not fire")
        return 1
    if live["standin"]["n_probe1_labels"] != live["standin"]["n_edges"]:
        print(
            "FAILED:ADV-0110-probe1 expected every stand-in edge to be a LABEL",
            live["standin"]["n_probe1_labels"],
            live["standin"]["n_edges"],
        )
        return 1
    if live["audit_sha256"] != doc.get("audit_sha256"):
        print("FAILED:ADV-0110-probe1 audit_sha256 drift")
        print(live["audit_sha256"])
        print(doc.get("audit_sha256"))
        return 1
    art_targets = doc.get("enumerated_targets") or []
    if not art_targets:
        print("FAILED:ADV-0110-probe1 no enumerated_targets")
        return 1
    live_by = {t["id"]: t["verdict"] for t in live["enumerated_targets"]}
    seen = set()
    for row in art_targets:
        tid = row.get("id")
        v = row.get("verdict")
        if tid in seen or v not in ALLOWED:
            print("FAILED:ADV-0110-probe1 bad target", tid, v)
            return 1
        if live_by.get(tid) != v:
            print("FAILED:ADV-0110-probe1 verdict drift", tid, v, live_by.get(tid))
            return 1
        seen.add(tid)
    if seen != set(live_by):
        print("FAILED:ADV-0110-probe1 target set mismatch")
        return 1
    payload = {
        "probe": "probe1-link-falsifiability",
        "unit_id": "ADV-0110",
        "pass": True,
        "audit_sha256": live["audit_sha256"],
        "control_probe1": control["probe1"],
        "planted_probe1": planted["probe1"],
        "standin_labels": live["standin"]["n_probe1_labels"],
        "standin_edges": live["standin"]["n_edges"],
        "syn0001_present": live["syn0001"]["present"],
        "n_targets": len(art_targets),
        "overall_verdict": live["overall_verdict"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"control={control['probe1']} planted={planted['probe1']} "
        f"labels={payload['standin_labels']}/{payload['standin_edges']} "
        f"targets={payload['n_targets']}"
    )
    print("SUCCESS:ADV-0110-probe1 per-link falsifiability re-derived and matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
