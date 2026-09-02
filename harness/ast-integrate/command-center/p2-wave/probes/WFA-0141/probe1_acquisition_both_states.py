#!/usr/bin/env python3
"""Probe 1: both-states acquisition gate (catalog tests_required)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

OUT = HERE / "probe1-acquisition-both-states.raw.json"


def main() -> int:
    planted = C.planted_bundle()
    catalog = C.candidate_catalog(planted["candidates"])
    own = C.acquire(catalog["plant-own-runner"])
    pure = C.acquire(catalog["plant-pure-mechanism"])
    lang = C.acquire(catalog["plant-language-only"])
    errors: list[str] = []
    if own["gate"] != "FIRE" or not own["over_one"]:
        errors.append(f"own-runner did not fire: {own}")
    if "langgraph" not in own["planes"]:
        errors.append(f"own-runner missing langgraph: {own['planes']}")
    if own["counter"] != "count_planes":
        errors.append("acquisition did not use count_planes")
    if pure["gate"] != "PASS" or pure["over_one"]:
        errors.append(f"pure-mechanism did not pass: {pure}")
    if C.HOME_PLANE not in pure["planes"] or len(pure["planes"]) != 1:
        errors.append(f"pure-mechanism planes {pure['planes']}")
    if lang["gate"] != "PASS" or lang["over_one"]:
        errors.append(f"language-only treated as a control plane: {lang}")
    report = {
        "probe": "probe1-acquisition-both-states",
        "unit_id": "WFA-0141",
        "own_runner": own,
        "pure_mechanism": pure,
        "language_only": lang,
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        print("FAILED:WFA-0141-probe1 " + "; ".join(errors))
        return 1
    print(json.dumps({"own_gate": own["gate"], "pure_gate": pure["gate"], "pass": True}))
    print(
        "SUCCESS:WFA-0141-probe1 own-runner fires at acquisition; "
        "pure-mechanism passes; language runtime is not a plane"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
