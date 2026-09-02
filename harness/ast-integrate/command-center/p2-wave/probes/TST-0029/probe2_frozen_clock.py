#!/usr/bin/env python3
"""Probe 2: frozen clock does not change the production DAG trace.

Isolates clock leakage by injecting FrozenClock vs WallClock, and PID leakage
by injecting FixedPid vs LivePid. Detector control: the same injections MUST
move the trace when leak modes are on. Planted Date.now() must be detected.
Schema must reject garbage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load_lib import repo  # noqa: E402
from measure import collect  # noqa: E402

REPO = repo()
RECEIPT = REPO / "command-center" / "receipts" / "TST-0029.json"
SCHEMA = REPO / "command-center" / "schema" / "test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0029"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0029-probe2 {msg}")
    return 1


def main() -> int:
    data = collect()
    flags = data["flags"]
    print(
        json.dumps(
            {
                "frozen_clock_unchanged": flags["frozen_clock_unchanged"],
                "fixed_pid_unchanged": flags["fixed_pid_unchanged"],
                "clock_leak_detector_fired": flags["clock_leak_detector_fired"],
                "pid_leak_detector_fired": flags["pid_leak_detector_fired"],
                "planted_date_now_detected": flags["planted_date_now_detected"],
                "clean_fixture_clean": flags["clean_fixture_clean"],
                "executor_source_clean": flags["executor_source_clean"],
                "frozen_vs_wall": data["frozen_vs_wall"],
                "fixed_vs_live_pid": data["fixed_vs_live_pid"],
                "pid_leak_injection": {
                    "pid_a": data["pid_leak_injection"]["pid_a"],
                    "pid_b": data["pid_leak_injection"]["pid_b"],
                    "fired": data["pid_leak_injection"]["fired"],
                    "order_a": data["pid_leak_injection"]["order_a"],
                    "order_b": data["pid_leak_injection"]["order_b"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not flags["frozen_clock_unchanged"]:
        return fail("frozen clock changed the production trace (clock leaked)")
    if not flags["fixed_pid_unchanged"]:
        return fail("fixed PID changed the production trace (PID leaked)")
    if not flags["clock_leak_detector_fired"]:
        return fail("clock-leak injection did not move the trace (detector silent)")
    if not flags["pid_leak_detector_fired"]:
        return fail("pid-leak injection did not move the trace (detector silent)")
    if data["pid_leak_injection"]["node_order_a"] == data["pid_leak_injection"]["node_order_b"]:
        return fail("pid leak hashes differed but node_order did not")
    if not flags["planted_date_now_detected"]:
        return fail("planted Date.now() was not detected")
    if not flags["clean_fixture_clean"]:
        return fail(f"clean fixture scanned dirty {data['banned_scan']['clean_fixture']}")
    if not flags["executor_source_clean"]:
        return fail(f"executor source has banned constructs {data['banned_scan']['executor']}")
    clock_hits = data["banned_scan"]["clock_module"]
    if not any(h.get("kind") == "wall-clock" for h in clock_hits):
        return fail("clock.py did not contain the wall-clock injection surface")
    if not any(h.get("kind") == "pid" for h in clock_hits):
        return fail("clock.py did not contain the pid injection surface")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = list(jsonschema.Draft7Validator(schema).iter_errors(garbage))
    print(f"garbage_schema_errors={len(g_errs)}")
    if not g_errs:
        return fail("schema accepted unrelated garbage")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("receipt sentinel absent")
    r_errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if r_errs:
        return fail(f"receipt schema {r_errs[0].message}")
    if doc.get("frozen_clock", {}).get("trace_unchanged") is not True:
        return fail("receipt frozen_clock.trace_unchanged is not true")
    if doc.get("fixed_pid", {}).get("trace_unchanged") is not True:
        return fail("receipt fixed_pid.trace_unchanged is not true")
    sources = doc.get("nondeterminism_sources") or []
    if len(sources) < 2:
        return fail("receipt did not enumerate injection-found sources")
    if not any(s.get("source") == "wall-clock" for s in sources):
        return fail("receipt omitted wall-clock source")
    if not any(s.get("source") == "pid" for s in sources):
        return fail("receipt omitted pid source")
    if any(s.get("leaks_into_production_dag") is True for s in sources):
        return fail("receipt claimed a production DAG leak that live injection did not see")
    print("SUCCESS:TST-0029-probe2 frozen clock does not change the trace")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
