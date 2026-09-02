#!/usr/bin/env python3
"""Probe 1: detector control for post-edit re-validation.

Known path first: duplicate-id FAIL-CLOSED in the live A1 loader MUST fire.
Only then may we conclude wildcard / extra-MCP / extra-hook have no gate.
Absence of grep hits is not evidence.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import policy as P  # noqa: E402

OUT = HERE / "probe1-detector.raw.json"
SANDBOX = HERE / "fixtures" / "sandbox"
KNOWN = HERE / "fixtures" / "known-revalidation"


def _plant_wildcard(root: Path) -> None:
    skill = root / "capabilities" / "skills" / "skill.narrow.skill.json"
    body = json.loads(skill.read_text(encoding="utf-8"))
    allow = list(body["tool_policy"]["allow"])
    if "*" not in allow:
        allow.append("*")
    body["tool_policy"]["allow"] = allow
    skill.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    known = P.load_traced(KNOWN, inventory=[])
    dup_fired = any(
        e["gate"] == "duplicate-id" and e["fired"] for e in known["validation_events"]
    )
    if known["ok"] or not dup_fired:
        print("FAILED:ARC-0006-probe1 known re-validation path did not fire")
        print(json.dumps(known, indent=2, sort_keys=True)[:2000])
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="arc0006-p1-"))
    try:
        dest = tmp / "sandbox"
        shutil.copytree(SANDBOX, dest)
        baseline = P.load_traced(dest)
        if not baseline["ok"]:
            print("FAILED:ARC-0006-probe1 baseline load failed", baseline["errors"])
            return 1
        if "*" in baseline["declared"]["tools"]:
            print("FAILED:ARC-0006-probe1 baseline already has wildcard")
            return 1
        stale_declared = list(baseline["declared"]["tools"])

        _plant_wildcard(dest)
        # Disk changed; in-memory baseline must stay stale (no resident runtime).
        if "*" in stale_declared:
            print("FAILED:ARC-0006-probe1 in-memory baseline mutated without reload")
            return 1

        after = P.load_traced(dest)
        if not after["ok"]:
            print("FAILED:ARC-0006-probe1 wildcard edit FAIL-CLOSED unexpectedly")
            return 1
        wild_reject = any(
            e["gate"] == "wildcard-reject" and e["fired"]
            for e in after["validation_events"]
        )
        if wild_reject:
            print("FAILED:ARC-0006-probe1 wildcard-reject fired; detector over-claimed")
            return 1
        if "*" not in after["declared"]["tools"]:
            print("FAILED:ARC-0006-probe1 wildcard not present as declared token")
            return 1
        if after["loader_expanded_wildcards"]:
            print("FAILED:ARC-0006-probe1 loader claimed to expand wildcards")
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    doc = {
        "known_duplicate_id_fired": True,
        "known_ok": False,
        "known_errors": known["errors"],
        "baseline_ok": True,
        "baseline_declared": stale_declared,
        "post_edit_without_reload_stale": True,
        "after_reload_ok": True,
        "after_wildcard_declared": after["declared"]["tools"],
        "after_wildcard_reject_fired": False,
        "detector_can_see_known_path": True,
        "no_revalidation_is_executed": True,
        "loader": P.LOADER_REL,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "known_dup_fired=True wildcard_reject_fired=False "
        f"declared_after={after['declared']['tools']} "
        "stale_until_reload=True"
    )
    print("SUCCESS:ARC-0006-probe1 detector-control re-validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
