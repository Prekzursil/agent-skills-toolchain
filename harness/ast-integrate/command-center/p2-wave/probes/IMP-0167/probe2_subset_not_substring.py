#!/usr/bin/env python3
"""Probe 2: reconciliation is a computed subset check, not a substring of prose.

Three traps a substring matcher fails:

1. Token-in-token: required {Read} vs grantable {ReadWrite}.
   Substring would grant ("Read" in "ReadWrite"); subset BLOCKS naming Read.
2. Prose mention: description contains "WebFetch", typed tools are {Read}.
   Substring-on-prose would BLOCK; subset IMPORTs (prose is not a requirement).
3. Silent typed requirement: description has no tool names, typed tools are
   {WebFetch}. Substring-on-prose would IMPORT; subset BLOCKS naming WebFetch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import  # noqa: E402

ensure_import()
from workflow_foundry.tool_requirements import (  # noqa: E402
    extract_tool_requirements,
    import_candidate,
    reconcile_subset,
)

FIX = HERE / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0167-probe2 {msg}")
    return 1


def prose_substring_missing(candidate: dict, grantable: list[str]) -> list[str]:
    """Banned detector: a tool name appearing in prose counts as a requirement."""
    blob = " ".join(
        str(candidate.get(k) or "")
        for k in ("description", "title", "notes", "prose", "summary")
    )
    catalog = [
        "Read",
        "Write",
        "Edit",
        "Grep",
        "Glob",
        "Bash",
        "WebFetch",
        "WebSearch",
    ]
    required_by_prose = {t for t in catalog if t in blob}
    return sorted(required_by_prose - set(grantable))


def token_in_token_substring_ok(required: set[str], grantable: set[str]) -> bool:
    """Banned detector: `needle in haystack_token` instead of set membership."""
    return all(any(r in g for g in grantable) for r in required)


def main() -> int:
    host = load("host_permissions.json")["grantable"]
    unit = load("unit_permissions.json")["tool_permissions"]

    ok, missing = reconcile_subset(["Read"], ["ReadWrite"])
    print(f"trap1 subset Read ⊆ {{ReadWrite}} ok={ok} missing={sorted(missing)}")
    if ok or missing != frozenset({"Read"}):
        return fail("subset check must BLOCK Read against grantable ReadWrite")
    if not token_in_token_substring_ok({"Read"}, {"ReadWrite"}):
        return fail("control: substring matcher did not fire on Read/ReadWrite")
    print("trap1 substring would GRANT; subset BLOCKS naming Read")

    prose = load("candidate_prose_mentions_webfetch.json")
    derived = extract_tool_requirements(prose)
    print(
        f"trap2 derived={sorted(derived)} "
        f"prose_substr_missing={prose_substring_missing(prose, host)}"
    )
    if "WebFetch" in derived:
        return fail("prose WebFetch leaked into typed requirements")
    if derived != frozenset({"Read"}):
        return fail(f"prose fixture derived {derived}, want {{Read}}")
    if "WebFetch" not in prose_substring_missing(prose, host):
        return fail("control: prose substring matcher did not flag WebFetch")
    decision_prose = import_candidate(
        prose, unit_permissions=unit, host_grantable=host
    )
    if decision_prose.status != "IMPORTED":
        return fail(f"prose-only mention BLOCKED: {decision_prose.as_dict()}")
    print("trap2 prose substring would BLOCK WebFetch; subset IMPORTs")

    silent = load("candidate_typed_webfetch_silent_prose.json")
    derived_s = extract_tool_requirements(silent)
    print(
        f"trap3 derived={sorted(derived_s)} "
        f"prose_substr_missing={prose_substring_missing(silent, host)}"
    )
    if derived_s != frozenset({"WebFetch"}):
        return fail(f"silent-prose fixture derived {derived_s}, want {{WebFetch}}")
    if prose_substring_missing(silent, host):
        return fail("control: prose substring matcher must miss silent typed WebFetch")
    decision_s = import_candidate(
        silent, unit_permissions=unit, host_grantable=host
    )
    if decision_s.status != "BLOCKED":
        return fail("typed WebFetch imported silently because prose was clean")
    if "WebFetch" not in decision_s.missing_capabilities:
        return fail(f"typed miss not named: {decision_s.missing_capabilities}")
    print("trap3 prose substring would IMPORT; subset BLOCKS naming WebFetch")

    if decision_prose.method != "set-subset" or decision_s.method != "set-subset":
        return fail("method is not set-subset")

    print("SUCCESS:IMP-0167-probe2 subset check computed, not substring of prose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
