#!/usr/bin/env python3
"""Probe 2: runtime coverage of non-test entry points.

An import is not a use: the module must actually execute (a call), not merely load.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

UNIT = "AUD-0031"


def main() -> int:
    runtime = E.live_runtime_trace()
    use = E.import_vs_use_control()
    payload = {
        "probe": "probe2-runtime-coverage",
        "unit_id": UNIT,
        "method": runtime.get("method"),
        "python_entries_attempted": runtime.get("python_entries_attempted"),
        "js_entries_attempted": runtime.get("js_entries_attempted"),
        "python_traces": runtime.get("python_traces"),
        "js_traces": runtime.get("js_traces"),
        "tools_lib_loaded": runtime.get("tools_lib_loaded"),
        "tools_lib_executed": runtime.get("tools_lib_executed"),
        "lib_home_exists": runtime.get("lib_home_exists"),
        "lib_home_file_count": runtime.get("lib_home_file_count"),
        "import_vs_use_control": use,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not use.get("passed"):
        print(
            f"FAILED:{UNIT}-probe2 import-vs-use "
            f"import_only_used={use.get('python_import_only_executed_used')} "
            f"execute_used={use.get('python_execute_executed_used')}"
        )
        return 1
    if use.get("python_import_only_executed_used"):
        print(f"FAILED:{UNIT}-probe2 import-only counted as execution")
        return 1
    if not use.get("python_execute_executed_used"):
        print(f"FAILED:{UNIT}-probe2 execute path did not record used()")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 runtime-coverage "
        f"py_entries={runtime.get('python_entries_attempted')} "
        f"executed_lib={len(runtime.get('tools_lib_executed') or [])} "
        f"import_vs_use=pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
