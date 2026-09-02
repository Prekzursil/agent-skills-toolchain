#!/usr/bin/env python3
"""Probe 1: AST scan of skip / skipif / skipUnless; resolve platform predicate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = C.REPO / "command-center/audit/AUD-0054-platform-conditional-tests.json"


def main() -> int:
    ast_doc = C.ast_census()
    errors: list[str] = []
    if not ast_doc["windows_control_in_decorator_scan"]:
        errors.append("windows-only control decorator not found")
    if not ast_doc["posix_control_in_decorator_scan"]:
        errors.append("posix-only control decorator not found")
    if ast_doc["runtime_control_in_decorator_scan"]:
        errors.append("runtime-only skip was found by decorator scan; probes not independent")
    if ast_doc["fixture_platform_gate_count"] < 2:
        errors.append("expected two platform decorator gates in the control fixture")

    payload = {
        "probe": "probe1-ast-decorators",
        "live_test_files": ast_doc["live_test_file_count"],
        "live_test_functions": ast_doc["live_test_function_count"],
        "live_platform_gated": ast_doc["live_platform_gate_count"],
        "fixture_platform_gated": ast_doc["fixture_platform_gate_count"],
        "windows_control": ast_doc["windows_control_in_decorator_scan"],
        "posix_control": ast_doc["posix_control_in_decorator_scan"],
        "runtime_control_in_ast": ast_doc["runtime_control_in_decorator_scan"],
        "platform_gates": ast_doc["platform_gates"],
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            errors.append(f"artifact self-declared {st}")
        recorded = (C.art_section(doc, "inventory").get("totals") or {}).get(
            "live_platform_gated"
        )
        if recorded is not None and int(recorded) != ast_doc["live_platform_gate_count"]:
            errors.append(
                f"artifact live_platform_gated={recorded} != live scan {ast_doc['live_platform_gate_count']}"
            )

    if errors:
        print("FAILED:AUD-0054-probe1 " + "; ".join(errors))
        return 1
    print(
        "live_files={0} live_tests={1} live_platform_gated={2} "
        "control_platform_gated={3} runtime_missed=True".format(
            ast_doc["live_test_file_count"],
            ast_doc["live_test_function_count"],
            ast_doc["live_platform_gate_count"],
            ast_doc["fixture_platform_gate_count"],
        )
    )
    print("SUCCESS:AUD-0054-probe1 AST skip/skipif platform predicates; runtime-only missed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
