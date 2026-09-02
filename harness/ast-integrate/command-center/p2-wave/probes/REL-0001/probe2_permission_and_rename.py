#!/usr/bin/env python3
"""Probe 2: permission widening is MAJOR with no key removed; pure rename is NONE."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bump_linter as L  # noqa: E402
import corpus as C  # noqa: E402


def run_case(name: str) -> tuple[int, dict, dict]:
    tmp = Path(tempfile.mkdtemp(prefix="rel0001-p2-"))
    old_tree = C.baseline()
    new_tree = C.CASES[name]()
    old = C.write_tree(tmp / "old", old_tree)
    new = C.write_tree(tmp / "new", new_tree)
    rc, doc = L.invoke_cli(old, new)
    return rc, doc, new_tree


def rule_ids(doc: dict) -> set[str]:
    return {str(r.get("rule_id")) for r in (doc.get("findings") or []) if isinstance(r, dict)}


def main() -> int:
    rc_perm, perm, perm_tree = run_case("major-permission-widen")
    rc_ren, ren, _ = run_case("rename-identical")

    errors: list[str] = []
    plugin = perm_tree["plugin.json"]
    required = ["name", "version", "description", "hooks", "tool_permissions"]
    missing = [k for k in required if k not in plugin]
    if missing:
        errors.append(f"permission case unexpectedly dropped keys {missing}")
    if rc_perm == 0:
        errors.append(f"permission widen declared PATCH must be non-zero, got {rc_perm}")
    if perm.get("derived_bump") != "MAJOR":
        errors.append(f"permission widen derived={perm.get('derived_bump')} want MAJOR")
    if "permission_widened" not in rule_ids(perm):
        errors.append(f"permission widen missing rule id, have {sorted(rule_ids(perm))}")
    if "required_manifest_key_removed" in rule_ids(perm):
        errors.append("permission widen must not be classified as key removal")

    if rc_ren != 0:
        errors.append(f"pure rename must be silent, got {rc_ren}")
    if ren.get("derived_bump") != "NONE":
        errors.append(f"pure rename derived={ren.get('derived_bump')} want NONE")
    if not ren.get("renames"):
        errors.append("pure rename produced no rename records")
    higher = [
        r
        for r in (ren.get("findings") or [])
        if str(r.get("bump")) in {"PATCH", "MINOR", "MAJOR"}
    ]
    if higher:
        errors.append(f"pure rename carried a bump finding: {higher[:3]}")

    out = {
        "probe": "probe2-permission-and-rename",
        "unit_id": "REL-0001",
        "permission_widen": {
            "linter_exit_code": rc_perm,
            "derived_bump": perm.get("derived_bump"),
            "declared_bump": perm.get("declared_bump"),
            "rule_ids": sorted(rule_ids(perm)),
            "required_keys_still_present": not missing,
            "added_permission": "Bash",
        },
        "pure_rename": {
            "linter_exit_code": rc_ren,
            "derived_bump": ren.get("derived_bump"),
            "declared_bump": ren.get("declared_bump"),
            "renames": ren.get("renames"),
        },
        "pass": not errors,
        "errors": errors,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"perm_rc={rc_perm} derived={perm.get('derived_bump')} "
        f"rename_rc={rc_ren} derived={ren.get('derived_bump')} "
        f"renames={ren.get('renames')}"
    )
    if errors:
        print("FAILED:REL-0001-probe2 " + "; ".join(errors))
        return 1
    print(
        "SUCCESS:REL-0001-probe2 permission widening is MAJOR with keys intact; "
        "byte-identical rename is no-bump-required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
