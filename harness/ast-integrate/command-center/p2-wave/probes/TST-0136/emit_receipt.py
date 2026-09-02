#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0136.json from live Retry-After measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    FALLBACK,
    IGNORE_BACKOFF,
    PROPERTY_N,
    honor_criteria,
    reconcile,
    result_to_dict,
    run_four_cases,
    run_property,
    run_scheduler_four,
)

OUT = "command-center/receipts/TST-0136.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/scheduler_report"
QUESTION = (
    "Does the client honor Retry-After when expressed as delta-seconds AND as "
    "an HTTP-date? PASS requires the observed next-attempt time to fall inside "
    "the instructed window for both forms, including a date already in the past "
    "(immediate retry) and a malformed value (fall back to backoff, do not crash)."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    fake_honor = run_four_cases(live=False, honor=True)
    fake_ignore = run_four_cases(live=False, honor=False)
    live_honor = run_four_cases(live=True, honor=True)
    live_ignore = run_four_cases(live=True, honor=False)
    scheduled = run_scheduler_four()
    prop_honor = run_property(honor=True)
    prop_ignore = run_property(honor=False)
    rec_fake = reconcile(fake_honor, live=False)
    rec_live = reconcile(live_honor, live=True)
    rec_prop = reconcile(prop_honor, live=False)

    honor_four = all(honor_criteria(r) for r in fake_honor + live_honor)
    ignore_four = not any(honor_criteria(r) for r in fake_ignore + live_ignore)
    sched_ok = all(s["ok"] for s in scheduled)
    prop_ok = all(honor_criteria(r) for r in prop_honor)
    ignore_prop_fail = sum(1 for r in prop_ignore if not honor_criteria(r))

    if not (honor_four and ignore_four and sched_ok and prop_ok):
        print("FAILED:TST-0136 emit measurements did not pass")
        return 1
    if ignore_prop_fail < 150:
        print(f"FAILED:TST-0136 ignore property fail count {ignore_prop_fail}")
        return 1
    if not (rec_fake["ok"] and rec_live["ok"] and rec_prop["ok"]):
        print("FAILED:TST-0136 clock reconciliation")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "tools/command-center/retry_after.py",
        "tools/command-center/arrival_scheduler.py",
        "tools/command-center/tests/test_retry_after.py",
        "command-center/p2-wave/probes/TST-0136/harness.py",
        "command-center/p2-wave/probes/TST-0136/probe1_four_wire_formats.py",
        "command-center/p2-wave/probes/TST-0136/probe2_property_and_reconciliation.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]

    receipt = {
        "unit_id": "TST-0136",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0136",
        "completion_sentinel": "SUCCESS:TST-0136",
        "title": "Retry-After is honored in both wire formats",
        "question": QUESTION,
        "report_kind": "scheduler_report",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "ts": now,
        "produced_by": {
            "role": "scheduler-tester",
            "execution_substrate": "linux-local",
            "cloud_ok": False,
        },
        "implementation": {
            "parser": "tools/command-center/retry_after.py",
            "scheduler": "tools/command-center/arrival_scheduler.py:dispatch_scheduled",
            "wire_forms": ["delta-seconds", "IMF-fixdate HTTP-date"],
            "past_date": "wait 0 (immediate retry)",
            "malformed": f"fallback {FALLBACK}s, no exception",
        },
        "tests": [
            {
                "id": "TST-0136-T1",
                "name": "delta-seconds honored (FakeClock + live HTTP)",
                "result": "PASS",
            },
            {
                "id": "TST-0136-T2",
                "name": "HTTP-date honored (FakeClock + live HTTP)",
                "result": "PASS",
            },
            {
                "id": "TST-0136-T3",
                "name": "past HTTP-date retries immediately",
                "result": "PASS",
            },
            {
                "id": "TST-0136-T4",
                "name": "malformed Retry-After falls back without crash",
                "result": "PASS",
            },
            {
                "id": "TST-0136-T5",
                "name": f"property test n={PROPERTY_N} including negative, zero, huge, malformed",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0136-NC1",
                "kind": "both-states",
                "description": (
                    "A client that ignores Retry-After and always waits "
                    f"{IGNORE_BACKOFF}s (live {2.5}s) must fail all four honor windows."
                ),
                "fired_on_bad_state": ignore_four,
                "silent_on_good_state": honor_four,
            }
        ],
        "evidence": [
            {
                "signal": "a",
                "name": "harness dispatch timestamps",
                "claim": (
                    "Client dispatch log next-attempt gaps match parsed Retry-After "
                    "for delta-seconds, HTTP-date, past date (0), and malformed fallback."
                ),
                "live_honor": [result_to_dict(r) for r in live_honor],
                "fake_honor": [result_to_dict(r) for r in fake_honor],
                "confidence": "almost-certain",
            },
            {
                "signal": "b",
                "name": "server fixture arrival log",
                "claim": (
                    "Independent server arrival timestamps reconcile with client "
                    "dispatch gaps (FakeClock skew 0; live HTTP skew < 150ms)."
                ),
                "reconcile_fake": rec_fake,
                "reconcile_live": rec_live,
                "reconcile_property": {
                    "pairs": rec_prop["pairs"],
                    "skew_fail": rec_prop["skew_fail"],
                    "gap_fail": rec_prop["gap_fail"],
                    "ok": rec_prop["ok"],
                },
                "confidence": "almost-certain",
            },
        ],
        "clock_reconciliation": {
            "method": "pair client dispatch[i] with server arrival[i]; compare gaps",
            "fake_ok": rec_fake["ok"],
            "live_ok": rec_live["ok"],
            "property_ok": rec_prop["ok"],
        },
        "property_test": {
            "n": PROPERTY_N,
            "honor_pass": sum(1 for r in prop_honor if honor_criteria(r)),
            "ignore_fail": ignore_prop_fail,
            "includes": ["negative", "zero", "huge", "malformed", "delta-seconds", "http-date"],
        },
        "dispatch_scheduled_string_headers": scheduled,
        "reviewer": {
            "reviewer_id": "TST-0136-probe2-property-and-reconciliation",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 recomputes expected waits from raw headers and checks "
                "client/server clock gaps independently of probe 1 summaries."
            ),
        },
        "artifacts": artifacts,
        "residual_unknowns": [
            "Vendor Claude/Codex adapters (IMP-0420/0421) are not on this worktree; "
            "the admission-layer client in arrival_scheduler.py is the unit under test."
        ],
        "cloud_ok": False,
        "notes": (
            "G-1 for TST-0136. cloud ok=true is not delivery. Did not run "
            "unit_manifest.py --write. SUCCESS:TST-0136"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    if "SUCCESS:TST-0136" not in text:
        print("FAILED:TST-0136 sentinel missing")
        return 1
    print("SUCCESS:TST-0136")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
