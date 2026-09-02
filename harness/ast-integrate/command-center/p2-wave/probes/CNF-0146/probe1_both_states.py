#!/usr/bin/env python3
"""Named probe 1: both-states (uninstalled vs installed) + no-contamination."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import scenario_both_states, scenario_no_contamination  # noqa: E402
import tempfile

ART = REPO / "command-center/receipts/CNF-0146.json"
SENTINEL = "SUCCESS:CNF-0146"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0146-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0146-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "CNF-0146":
        print("FAILED:CNF-0146-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0146-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="cnf0146-p1-") as tmp:
        root = Path(tmp)
        both = scenario_both_states(root)
        clean = scenario_no_contamination(root)

    payload = {
        "probe": "probe1-both-states-no-contamination",
        "unit_id": "CNF-0146",
        "pass": True,
        "both_states": both,
        "no_contamination": clean,
        "receipt_state": doc.get("state"),
        "verdict": doc.get("verdict"),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "uninstalled_loaded="
        f"{both['uninstalled_loaded_count']} installed_loaded="
        f"{both['installed_loaded_count']} fresh_hits={clean['fresh_hits']}"
    )
    print("SUCCESS:CNF-0146-probe1 both-states and no-contamination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
