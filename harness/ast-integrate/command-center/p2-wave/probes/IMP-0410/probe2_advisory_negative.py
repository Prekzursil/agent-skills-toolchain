#!/usr/bin/env python3
"""Probe 2: advisory writes and unleased negative control.

Advisory: a non-holder write to a leased path is never refused and still
produces a conflict event. Negative control: a write to an unleased path
produces no conflict event. A blocking mutant of note_write must fail the
advisory assertion (both-states).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

RECEIPT = S.REPO / "command-center" / "receipts" / "IMP-0410.json"


def check_receipt() -> str | None:
    if not RECEIPT.is_file():
        return None
    text = RECEIPT.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"receipt self-declared {doc.get('state')}"
    if "SENTINEL:IMP-0410:LEASES-ADVISORY-LOGGED" not in text:
        return "sentinel-absent"
    excerpt = doc.get("event_log_excerpt") or []
    if not excerpt:
        return "event-log-excerpt-absent"
    for ev in excerpt:
        if ev.get("event") != "lease-conflict":
            return "excerpt-not-conflict"
        if ev.get("write_allowed") is not True or ev.get("write_succeeded") is not True:
            return "excerpt-write-not-advisory"
        if ev.get("writer_session") == ev.get("holder_session"):
            return "excerpt-not-non-holder"
    tests = doc.get("tests") or {}
    for key in ("advisory", "unleased_negative_control"):
        row = tests.get(key) or {}
        if row.get("pass") is not True:
            return f"receipt test {key} not PASS"
    policy = doc.get("policy") or {}
    if policy.get("advisory") is not True or policy.get("writes_never_refused") is not True:
        return "policy-not-advisory"
    return None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0410-p2-") as td:
        tmp = Path(td)
        advisory = S.run_advisory(tmp)
        unleased = S.run_unleased_negative(tmp)
        mutant = S.blocking_mutant_refuses(tmp)
    print(
        json.dumps(
            {"advisory": advisory, "unleased": unleased, "mutant": mutant},
            sort_keys=True,
        )
    )
    print(
        f"advisory pass={advisory['pass']} refused={advisory['refused']} "
        f"conflict={advisory['conflict']} on_disk={advisory['on_disk']!r}"
    )
    print(
        f"unleased pass={unleased['pass']} conflict_count={unleased['conflict_event_count']} "
        f"refused={unleased['refused']}"
    )
    print(
        f"mutant pass={mutant['pass']} live_refused={mutant['live_refused']} "
        f"mutant_refused={mutant['mutant_refused']}"
    )
    if not advisory["pass"]:
        print("FAILED:IMP-0410-probe2 advisory")
        return 1
    if not unleased["pass"]:
        print("FAILED:IMP-0410-probe2 unleased-negative-control")
        return 1
    if not mutant["pass"]:
        print("FAILED:IMP-0410-probe2 blocking-mutant-did-not-discriminate")
        return 1
    rec_err = check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0410-probe2 receipt {rec_err}")
        return 1
    print("SUCCESS:IMP-0410-probe2 advisory and unleased negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
