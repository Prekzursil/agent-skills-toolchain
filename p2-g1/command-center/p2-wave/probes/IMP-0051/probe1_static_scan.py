#!/usr/bin/env python3
"""IMP-0051 probe1: static scan - every raise site carries a taxonomy code.

Walks every production .py under platform/plugin, finds every ``raise
PluginError(...)`` site, extracts the code literal and requires it to be a
declared TAXONOMY code. Also proves the emitted taxonomy document satisfies
its declared schema (minItems pinned to the class count, unique codes and
exit codes, every next_command non-empty).
"""
from __future__ import annotations

import ast
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "platform"))

from plugin.errors import BY_CODE, taxonomy_document  # noqa: E402


def scan_raise_sites() -> dict[str, object]:
    total = 0
    coded = 0
    uncoded: list[str] = []
    unknown_codes: list[str] = []
    for py in sorted((REPO / "platform" / "plugin").rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            call = node.exc
            if isinstance(call, ast.Call):
                func = call.func
                name = func.id if isinstance(func, ast.Name) else (
                    func.attr if isinstance(func, ast.Attribute) else "")
            elif isinstance(call, ast.Name):
                name = call.id  # re-raise of a pre-built error object
            else:
                name = ""
            if "PluginError" not in name:
                continue
            total += 1
            if isinstance(call, ast.Call) and call.args:
                arg0 = call.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    code = arg0.value
                    if code in BY_CODE:
                        coded += 1
                    else:
                        unknown_codes.append(f"{py.name}:{node.lineno}:{code}")
                else:
                    uncoded.append(f"{py.name}:{node.lineno}:non-literal-code")
            else:
                # pre-constructed error: the construction site is elsewhere;
                # count as coded only if a literal construction exists in file
                src = py.read_text(encoding="utf-8")
                if 'PluginError("' in src or "PluginError('" in src:
                    coded += 1
                else:
                    uncoded.append(f"{py.name}:{node.lineno}:indirect")
    return {
        "total_raise_sites": total,
        "coded_raise_sites": coded,
        "uncoded_raise_sites": uncoded,
        "unknown_codes": unknown_codes,
    }


def schema_checks(doc: dict[str, object]) -> dict[str, bool]:
    classes = doc.get("classes") or []
    codes = [c.get("code") for c in classes]
    exits = [c.get("exit_code") for c in classes]
    return {
        "artifact_const": doc.get("artifact") == "error-taxonomy",
        "class_count_16": len(classes) == 16,
        "codes_unique": len(codes) == len(set(codes)),
        "exit_codes_unique": len(exits) == len(set(exits)),
        "next_command_nonempty": all(c.get("next_command") for c in classes),
        "fail_mode_valid": all(c.get("fail_mode") in ("fail-closed", "fail-open")
                               for c in classes),
    }


def main() -> int:
    scan = scan_raise_sites()
    doc = taxonomy_document()
    sch = schema_checks(doc)
    checks = {
        "every_raise_coded": len(scan["uncoded_raise_sites"]) == 0,  # type: ignore[arg-type]
        "every_code_declared": len(scan["unknown_codes"]) == 0,  # type: ignore[arg-type]
        "raise_sites_present": scan["total_raise_sites"] > 0,  # type: ignore[operator]
    }
    checks.update(sch)  # type: ignore[arg-type]
    out = {
        "probe": "probe1-static-scan",
        "unit_id": "IMP-0051",
        "scan": scan,
        "schema_checks": sch,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    print(f"raise_sites={scan['total_raise_sites']} coded={scan['coded_raise_sites']} "
          f"uncoded={len(scan['uncoded_raise_sites'])} classes={len(doc.get('classes') or [])}")
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        print(f"FAILED:IMP-0051-probe1 {failed}")
        return 1
    print("SUCCESS:IMP-0051-probe1 every raise site carries a declared taxonomy code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
