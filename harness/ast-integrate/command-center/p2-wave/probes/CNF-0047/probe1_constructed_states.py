#!/usr/bin/env python3
"""Probe 1: killed-mid-write vs clean finish; mtime-only is the broken control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0047-monitor-liveness.json"
SENTINEL = (
    "SUCCESS:CNF-0047 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both constructed states "
    "were monitored and the data source behind each verdict is named in the "
    "artifact. Any other terminal state is FAILED:CNF-0047 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    pair = S.constructed_pair()
    printable = {
        "states_report_differently": pair["states_report_differently"],
        "mtime_only_indistinguishable": pair["mtime_only_indistinguishable"],
        "killed_verdict": pair["killed"]["monitor"]["verdict"],
        "finished_verdict": pair["finished"]["monitor"]["verdict"],
        "killed_source": pair["killed"]["monitor"]["data_source"],
        "finished_source": pair["finished"]["monitor"]["data_source"],
        "killed_mtime_only": pair["killed"]["mtime_only"]["verdict"],
        "finished_mtime_only": pair["finished"]["mtime_only"]["verdict"],
        "mtime_used_killed": pair["killed"]["monitor"]["mtime_used"],
        "mtime_used_finished": pair["finished"]["monitor"]["mtime_used"],
        "source_audit_clean": pair["mtime_source_audit"]["clean"],
        "pass": pair["pass"],
    }
    print(json.dumps(printable, sort_keys=True))
    if not pair["pass"]:
        print("FAILED:CNF-0047-probe1 constructed states did not discriminate")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0047-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0047-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0047-probe1 sentinel-absent")
        return 1
    states = {s.get("id"): s for s in (doc.get("constructed_states") or []) if isinstance(s, dict)}
    killed = states.get("killed-mid-write") or {}
    finished = states.get("finished-clean") or {}
    if killed.get("monitor_verdict") == finished.get("monitor_verdict"):
        print("FAILED:CNF-0047-probe1 artifact states indistinguishable")
        return 1
    if not killed.get("data_source") or not finished.get("data_source"):
        print("FAILED:CNF-0047-probe1 unnamed data source")
        return 1
    if killed.get("mtime_used") or finished.get("mtime_used"):
        print("FAILED:CNF-0047-probe1 artifact used mtime")
        return 1
    ctrl = doc.get("mtime_only_control") or {}
    if not ctrl.get("indistinguishable") or not ctrl.get("fired_on_bad_state"):
        print("FAILED:CNF-0047-probe1 mtime-only control did not fire")
        return 1
    print(
        "SUCCESS:CNF-0047-probe1 constructed-states "
        f"{printable['killed_verdict']} vs {printable['finished_verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
