#!/usr/bin/env python3
"""Probe 1: mutate one translation gate (fail) vs intact (pass), all cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as B  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0155-translation-fidelity-oracle-for-the-translate-route.json"
)


def main() -> int:
    live = B.run()
    checks = [
        ("intact_pass", live.get("intact_pass")),
        ("mutant_fail", live.get("mutant_fail")),
        ("cases_intact_all_match", live.get("cases_intact_all_match")),
        (
            "oracle_named_the_gate",
            live.get("mutated_gate", {}).get("oracle_named_the_gate"),
        ),
        ("pass", live.get("pass")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:WFA-0155-probe1 {name}")
            return 1
    rows = live.get("intact_rows") or []
    if len(rows) != 3:
        print(f"FAILED:WFA-0155-probe1 expected 3 cases got {len(rows)}")
        return 1
    expected_stops = {
        "case-pass": "exhausted",
        "case-stop-score": "gate_fail",
        "case-stop-approved": "gate_fail",
    }
    expected_stages = {
        "case-pass": ["ingest", "review", "ship"],
        "case-stop-score": ["ingest"],
        "case-stop-approved": ["ingest", "review"],
    }
    for row in rows:
        cid = row["case_id"]
        stop = (row.get("stop") or {}).get("reason")
        stages = row.get("stages_entered")
        print(f"case {cid} stop={stop} stages={stages}")
        if stop != expected_stops.get(cid) or stages != expected_stages.get(cid):
            print(f"FAILED:WFA-0155-probe1 case {cid}")
            return 1
    named = live["mutated_gate"]["oracle_named"]
    print(f"mutant_named_gate={named}")
    if not ART.is_file():
        print("FAILED:WFA-0155-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0155-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0155" not in text:
        print("FAILED:WFA-0155-probe1 sentinel absent")
        return 1
    bs = doc.get("both_states") or {}
    if bs.get("intact_pass") is not True or bs.get("mutant_fail") is not True:
        print("FAILED:WFA-0155-probe1 artifact both_states drift")
        return 1
    mg = bs.get("mutated_gate") or {}
    if mg.get("stage") != "review" or mg.get("field") != "score":
        print("FAILED:WFA-0155-probe1 artifact mutated_gate drift")
        return 1
    print("SUCCESS:WFA-0155-probe1 both-states intact-pass mutant-fail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
