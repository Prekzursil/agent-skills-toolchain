#!/usr/bin/env python3
"""Probe 2: the probe reads commit charge, not working set.

Catalog test: test_probe_reads_commit_charge_not_working_set
A working-set probe is silent in the failing (commit-exhaustion) state.
Mechanically different from probe 1: fixture both-states, meminfo field
binding, live untouched-mmap divergence, and guard-source inspection.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from checks import probe2_live  # noqa: E402

ART = REPO / "command-center/receipts/TST-0103.json"
SENTINEL = "SUCCESS:TST-0103"


def _check_receipt(live: dict) -> list[str]:
    errors: list[str] = []
    if not ART.is_file():
        errors.append("receipt missing")
        return errors
    try:
        doc = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"receipt unparseable: {type(exc).__name__}")
        return errors
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        errors.append("sentinel absent")
    ws = doc.get("working_set_control") or {}
    live_fs = live.get("failing_state") or {}
    if ws.get("silent_in_commit_exhaustion") is not True:
        errors.append("receipt does not record working-set silence in failing state")
    if live_fs.get("working_set_guard_silent") is not True:
        errors.append("live working-set guard was not silent in failing state")
    bind = doc.get("parser_binding") or {}
    if bind.get("commit_field") != "Committed_AS":
        errors.append("receipt parser_binding.commit_field is not Committed_AS")
    if bind.get("working_set_field") != "Active":
        errors.append("receipt parser_binding.working_set_field is not Active")
    counters = doc.get("counters_sampled") or []
    names = {c.get("name") for c in counters if isinstance(c, dict)}
    if "commit_charge" not in names or "available_commit" not in names:
        errors.append("receipt counters_sampled missing commit_charge or available_commit")
    return errors


def main() -> int:
    live, errors = probe2_live()
    print(
        json.dumps(
            {
                "probe": "probe2",
                "failing_state": live.get("failing_state"),
                "ram_pressure_state": live.get("ram_pressure_state"),
                "parser_binding": live.get("parser_binding"),
                "guard_source_is_commit_charge": live.get("guard_source_is_commit_charge"),
                "mmap_ok": live.get("mmap_ok"),
                "mmap_skipped": bool((live.get("mmap") or {}).get("skipped")),
                "host_commit_ne_ws": (live.get("host") or {}).get(
                    "commit_charge_ne_working_set"
                ),
            },
            sort_keys=True,
        )
    )
    if ART.is_file():
        errors.extend(_check_receipt(live))
    if errors:
        for e in errors:
            print(f"FAILED:TST-0103-probe2 {e}")
        return 1
    print("SUCCESS:TST-0103-probe2 commit-charge probe; working-set silent in failing state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
