#!/usr/bin/env python3
"""Probe 1: runner exit code per catalog-gap step (live re-stat + re-run)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

ART = C.REPO / C.OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0042-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:AUD-0042-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != C.UNIT:
        print("FAILED:AUD-0042-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0042-probe1 self-declared", doc.get("state"))
        return 1
    gap = doc.get("gap_steps") or []
    if len(gap) != 32:
        print("FAILED:AUD-0042-probe1 gap_steps", len(gap))
        return 1
    missing_exit = [s["name"] for s in gap if not isinstance(s.get("exit_code"), int)]
    if missing_exit:
        print("FAILED:AUD-0042-probe1 missing exit_code", missing_exit[:5])
        return 1
    runs = json.loads(C.STEPS_JSON.read_text(encoding="utf-8"))
    live_mismatch = []
    for recorded, live in zip(gap, runs["gap_32"]):
        if recorded["name"] != live["name"]:
            live_mismatch.append(("name", recorded["name"], live["name"]))
            continue
        if recorded["exit_code"] != live["exit_code"]:
            live_mismatch.append(("exit", recorded["name"], recorded["exit_code"], live["exit_code"]))
        present_now = [p for p in live["extracted_paths"] if (C.REPO / p).exists()]
        if present_now != live["present_paths"]:
            live_mismatch.append(("present", recorded["name"], present_now, live["present_paths"]))
    # Re-run isolation (catalog gap step that is actually executable here).
    iso_code, iso_out = C.run_cmd(C.isolation_argv(), timeout=20)
    iso_ok = iso_code == 0 and "OK: shared interpreter is clean" in iso_out
    # Re-run one missing-file pytest: exit must be non-zero and collect nothing.
    miss_code, miss_out = C.run_cmd(
        C.pytest_argv("ci/tests/test_rules_doc_contracts.py"), timeout=20
    )
    miss_sum = C.parse_summary(miss_out)
    miss_ok = miss_code != 0 and miss_sum["collected"] == 0 and not miss_sum["counted_as_test_success"]
    passed = (
        not missing_exit
        and not live_mismatch
        and iso_ok
        and miss_ok
        and all(s.get("counted_as_test_success") is False or s.get("collected", 0) > 0 for s in gap)
    )
    payload = {
        "probe": "probe1-exit-codes",
        "unit_id": C.UNIT,
        "pass": passed,
        "gap_steps": len(gap),
        "missing_exit": missing_exit,
        "live_mismatch_count": len(live_mismatch),
        "isolation_exit": iso_code,
        "isolation_ok": iso_ok,
        "missing_file_exit": miss_code,
        "missing_file_collected": miss_sum["collected"],
        "missing_file_ok": miss_ok,
    }
    print(json.dumps(payload, sort_keys=True))
    if not passed:
        print("FAILED:AUD-0042-probe1 exit-code ledger")
        print(json.dumps(live_mismatch[:8], default=str))
        return 1
    print(
        f"SUCCESS:AUD-0042-probe1 32 exit codes recorded; isolation rc={iso_code}; "
        f"missing-file pytest rc={miss_code} collected={miss_sum['collected']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
