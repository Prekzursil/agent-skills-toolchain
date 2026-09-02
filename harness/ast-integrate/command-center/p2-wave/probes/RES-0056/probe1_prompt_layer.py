#!/usr/bin/env python3
"""Named probe 1: prompt-layer self-violation is not stopped."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from permission_layers import run_demonstration  # noqa: E402

ART = REPO / "command-center/research/RES-0056.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        print("FAILED:RES-0056-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0056":
        print("FAILED:RES-0056-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:RES-0056" not in text:
        print("FAILED:RES-0056-probe1 sentinel absent")
        return 1
    if "prompt-layer violation that was not stopped" not in text:
        print("FAILED:RES-0056-probe1 sentinel phrase absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0056-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="res0056-p1-") as tmp:
        demo = run_demonstration(Path(tmp))
        leftover = list(Path(tmp).rglob("VIOLATION.txt"))

    if not demo["prompt_layer_violation_not_stopped"]:
        print("FAILED:RES-0056-probe1 prompt layer stopped the violation")
        return 1
    if demo["skill_prompt"]["declared_tools"] != ["Read"]:
        print("FAILED:RES-0056-probe1 declared", demo["skill_prompt"]["declared_tools"])
        return 1
    if "Write" not in demo["skill_prompt"]["requested_tools"]:
        print("FAILED:RES-0056-probe1 skill did not request Write")
        return 1
    if "Write" not in demo["rule_prompt"]["requested_tools"]:
        print("FAILED:RES-0056-probe1 rule did not request Write")
        return 1
    if leftover:
        print("FAILED:RES-0056-probe1 prompt layer wrote a file", leftover)
        return 1
    if not doc["demonstrations"]["prompt_layer_violation_not_stopped"]:
        print("FAILED:RES-0056-probe1 artifact demo flag false")
        return 1

    print(json.dumps({
        "skill_declared": demo["skill_prompt"]["declared_tools"],
        "skill_requested": demo["skill_prompt"]["requested_tools"],
        "skill_stopped": demo["skill_prompt"]["stopped"],
        "rule_stopped": demo["rule_prompt"]["stopped"],
        "classification": "DECLARED",
        "injected": True,
        "file_written_at_prompt_layer": False,
    }, sort_keys=True))
    print("prompt_not_stopped=True write_absent=True theatre=True")
    print("SUCCESS:RES-0056-probe1 prompt-layer violation was not stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
