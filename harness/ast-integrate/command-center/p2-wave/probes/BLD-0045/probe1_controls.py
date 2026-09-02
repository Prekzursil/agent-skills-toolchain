#!/usr/bin/env python3
"""Named probe 1: four catalog controls, live, plus receipt green-not-live check.

Control: a function called only for its side effect with no assertion must be reported.
Control: a function whose return value feeds an assert must NOT be reported.
Control: an except-branch that is covered but whose effect is never asserted must be reported.
Instrument control: prove branch coverage is on by observing a partial-branch entry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0045.json"
SENTINEL = "SUCCESS:BLD-0045"


def main() -> int:
    live = A.census()
    if not live["controls_pass"]:
        print("FAILED:BLD-0045-probe1 live controls")
        for row in live["controls"]:
            print(f"  {row['id']} {row['result']}")
        return 1
    for row in live["controls"]:
        print(f"{row['id']}={row['result']}")

    report = live["report"]
    unasserted = {
        f.get("function")
        for f in report["findings"]
        if f.get("class") == "COVERED-UNASSERTED"
    }
    if "side_effect_only" not in unasserted:
        print("FAILED:BLD-0045-probe1 side_effect_only not reported")
        return 1
    if "asserted_value" in unasserted:
        print("FAILED:BLD-0045-probe1 asserted_value falsely reported")
        return 1
    excepts = [
        f for f in report["findings"] if f.get("class") == "EXCEPT-COVERED-UNASSERTED"
    ]
    if not any(f.get("function") == "apply_with_rollback" for f in excepts):
        print("FAILED:BLD-0045-probe1 except-branch not reported")
        return 1
    partials = [p for p in report["partial_branch_entries"] if p.get("status") == "partial"]
    if not partials:
        print("FAILED:BLD-0045-probe1 no partial-branch entry")
        return 1
    if report["partial_when_branch_disabled"]:
        print("FAILED:BLD-0045-probe1 line-only mode still emitted partials")
        return 1
    if live["b08"]["status"] == "PRESENT" and not live["b08"]["found"]:
        print("FAILED:BLD-0045-probe1 b08 PRESENT with empty found list")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0045-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:BLD-0045-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0045-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("unit_id") != "BLD-0045":
        print("FAILED:BLD-0045-probe1 unit_id mismatch")
        return 1
    if doc.get("report_global_percentage") is not False:
        print("FAILED:BLD-0045-probe1 global percentage not explicitly omitted")
        return 1
    art_ids = {f.get("id") for f in (doc.get("findings") or [])}
    live_ids = {f.get("id") for f in report["findings"]}
    if art_ids != live_ids:
        print(f"FAILED:BLD-0045-probe1 finding-id drift live={live_ids} art={art_ids}")
        return 1
    art_unasserted = {
        f.get("function")
        for f in (doc.get("findings") or [])
        if f.get("class") == "COVERED-UNASSERTED"
    }
    if "asserted_value" in art_unasserted:
        print("FAILED:BLD-0045-probe1 receipt overclaims asserted_value as unasserted")
        return 1
    inst = doc.get("instrumentation") or {}
    if inst.get("branch_enabled") is not True:
        print("FAILED:BLD-0045-probe1 receipt branch_enabled is not true")
        return 1
    if not any(p.get("status") == "partial" for p in (inst.get("partial_branch_entries") or [])):
        print("FAILED:BLD-0045-probe1 receipt missing partial-branch entry")
        return 1
    b08 = doc.get("b08_suite_coverage") or {}
    if b08.get("status") == "PRESENT" and not b08.get("found"):
        print("FAILED:BLD-0045-probe1 receipt claims B08 PRESENT without paths")
        return 1
    print(
        f"side_effect={('side_effect_only' in unasserted)} "
        f"asserted_clean={('asserted_value' not in unasserted)} "
        f"except={len(excepts)} partial={len(partials)} b08={live['b08']['status']}"
    )
    print("SUCCESS:BLD-0045-probe1 four catalog controls plus receipt parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
