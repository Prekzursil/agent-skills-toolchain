#!/usr/bin/env python3
"""AUD-0054 tests_required control: probe1/probe2 independence on a runtime-only skip.

Catalog wording: "a runtime-only skip (raised inside the test body) must be found by
probe 2 and missed by probe 1; if both find it, the pair is not independent."

This script does NOT re-run anything -- it reads the two probes' own JSON output and
asserts the cross-condition mechanically, on TWO separate cases so the control is not
a single accidental coincidence:

  1. the hermetic fixture built for this unit
     (fixtures/test_control_runtime_only_skip.py), which has zero external
     dependencies and cannot bit-rot; and
  2. a real production test (tools/agentrail/tests/test_deploy.py) that already
     carried this exact pattern before this unit existed, discovered by grep rather
     than planted.

Both must satisfy: found_by_probe2=True AND found_by_probe1=False. If EITHER case
flips found_by_probe1 to True, the probes are not independent and this control FAILS
closed (exit 1) rather than silently passing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "control-probe-independence.json"
OUT_RAW = PROBE / "control-probe-independence.raw.txt"

CASES = [
    (
        "hermetic-fixture",
        "command-center/p2-wave/probes/AUD-0054/fixtures/test_control_runtime_only_skip.py",
        "test_control_windows_only_runtime_skip_no_decorator",
    ),
    (
        "real-production-test",
        "tools/agentrail/tests/test_deploy.py",
        "test_the_rendered_shim_really_propagates_a_nonzero_exit",
    ),
]


def main() -> int:
    p1 = json.loads((PROBE / "probe1-ast-platform-skips.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-collect-vs-execute.json").read_text(encoding="utf-8"))

    probe1_rows = p1.get("rows", [])
    probe2_runtime_only = {
        (r["path"], r["test_name"]) for r in p2.get("runtime_only_hits", [])
    }
    probe2_all_skipped = {
        (r["path"], r["test_name"])
        for f in p2.get("files", [])
        for r in f.get("skip_rows", [])
    }

    results = []
    all_ok = True
    for label, path, test_name in CASES:
        found_by_probe1 = any(
            r["path"] == path and r["target"] == test_name for r in probe1_rows
        )
        found_by_probe2 = (path, test_name) in probe2_all_skipped
        independent = found_by_probe2 and not found_by_probe1
        if not independent:
            all_ok = False
        results.append(
            {
                "case": label,
                "path": path,
                "test_name": test_name,
                "found_by_probe1": found_by_probe1,
                "found_by_probe2": found_by_probe2,
                "independent": independent,
            }
        )

    doc = {
        "unit": "AUD-0054",
        "control": "probe-independence-runtime-only-skip",
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cases": results,
        "ok": all_ok and len(results) == len(CASES),
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw = [
        "SUCCESS:AUD-0054-control-independence" if doc["ok"] else "FAILED:AUD-0054-control-independence",
        "unit=AUD-0054 control=probe-independence-runtime-only-skip",
    ]
    for r in results:
        raw.append(
            f"{r['case']}: {r['path']}::{r['test_name']} "
            f"found_by_probe1={r['found_by_probe1']} found_by_probe2={r['found_by_probe2']} "
            f"independent={r['independent']}"
        )
    raw.append(f"all_ok={doc['ok']}")
    OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8"))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
