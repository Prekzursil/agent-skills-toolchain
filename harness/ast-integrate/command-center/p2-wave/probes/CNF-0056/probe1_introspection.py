#!/usr/bin/env python3
"""Named probe 1: listings come from introspection; grep would count private helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/confirmation/CNF-0056-api-surface-diff.json"

sys.path.insert(0, str(HERE))
import schema_offline as SO  # noqa: E402
import surface as SF  # noqa: E402


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0056-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errors = SO.validate_doc(doc)
    if errors:
        print("FAILED:CNF-0056-probe1 schema-invalid")
        for line in errors[:20]:
            print(" ", line)
        return 1
    payload = SO.artifact_payload(doc)
    sentinel = (
        "SUCCESS:CNF-0056 emitted only when the artifact at output_path exists"
    )
    blob = json.dumps(doc)
    if sentinel not in blob or "SUCCESS:CNF-0056" not in blob:
        print("FAILED:CNF-0056-probe1 sentinel absent")
        return 1
    if payload.get("method") != "introspection":
        print("FAILED:CNF-0056-probe1 method is not introspection")
        return 1
    if payload.get("introspection_not_text_search") is not True:
        print("FAILED:CNF-0056-probe1 introspection flag false")
        return 1
    for label in ("before", "after"):
        surf = payload.get(label) or {}
        if surf.get("production_method") != "introspection":
            print(f"FAILED:CNF-0056-probe1 {label} not introspection")
            return 1

    after = SF.enumerate_surface(HERE / "fixtures" / "after", "cnf0056_probe1_after")
    control = SF.grep_control(HERE / "fixtures" / "after", after["symbols"])
    if "_secret_scale" not in control["private_helpers_grep_only"]:
        print("FAILED:CNF-0056-probe1 grep control did not catch _secret_scale")
        print(json.dumps(control, indent=2))
        return 1
    short = {s.split(".")[-1] for s in after["symbols"]}
    if "_secret_scale" in short:
        print("FAILED:CNF-0056-probe1 introspection leaked a private helper")
        return 1
    if "PublicAlpha" not in short:
        print("FAILED:CNF-0056-probe1 introspection missed PublicAlpha")
        return 1
    if after["symbols"] != payload["after"]["symbols"]:
        print("FAILED:CNF-0056-probe1 live introspection disagrees with artifact")
        print("live", after["symbols"])
        print("art ", payload["after"]["symbols"])
        return 1
    if after["cli_commands"] != payload["after"]["cli_commands"]:
        print("FAILED:CNF-0056-probe1 CLI tree disagrees with artifact")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-introspection-not-grep",
                "unit_id": "CNF-0056",
                "introspection_symbols": after["symbols"],
                "grep_private_only": control["private_helpers_grep_only"],
                "pass": True,
            },
            indent=2,
        )
    )
    print("SUCCESS:CNF-0056-probe1 introspection listings exclude private helpers grep would count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
