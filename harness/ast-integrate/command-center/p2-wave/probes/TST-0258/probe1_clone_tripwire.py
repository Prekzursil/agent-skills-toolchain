#!/usr/bin/env python3
"""Probe 1: detector-control first — planted clones must FIRE, then remediate.

A log line is not enough. After the trip-wire event there must be a later
round that records at least one independent position. Two runs on the same
spec must be byte-identical. Receipt numbers must match this live run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
from tools.council.antifail import unanimity as U  # noqa: E402

ART = E.RECEIPT


def fail(msg: str) -> int:
    print(f"FAILED:TST-0258-probe1 {msg}")
    return 1


def main() -> int:
    spec = E.load_clone()
    roster = E.roster(spec)
    transcript, identical = E.twice_identical(spec, remediation="full")
    events = transcript["events"]
    report = U.remediation_report(events, roster)
    tw = transcript.get("tripwire") or {}

    print(
        json.dumps(
            {
                "cast": roster,
                "cosmetic": report.get("cosmetic"),
                "fired": bool(tw.get("fired") and report.get("fired")),
                "identical_two_runs": identical,
                "independent_count": report.get("independent_count"),
                "independent_actors": [p.get("actor") for p in report.get("independent_positions") or []],
                "remediation_round": report.get("remediation_round"),
                "span": report.get("span"),
                "threshold_number": report.get("threshold_number") or U.THRESHOLD_ROUNDS,
                "tripwire_seq": report.get("tripwire_seq"),
                "unanimous_option": report.get("unanimous_option"),
            },
            sort_keys=True,
        )
    )
    print("cite " + U.cite_snippet(events, roster))

    if not identical:
        return fail("two runs on the clone spec were not byte-identical")
    if not report.get("fired") or not tw.get("fired"):
        return fail("planted clone unanimity did not fire the trip-wire")
    if not report.get("remediation_round_present"):
        return fail("trip-wire logged but no remediating round in the transcript")
    if report.get("cosmetic") or not (report.get("independent_count") or 0):
        return fail("remediation is cosmetic: no independent position after the trip-wire")
    critics = [p for p in report.get("independent_positions") or [] if p.get("actor") == "critic-independent"]
    if not critics:
        return fail("independent critic position missing from remediating round")
    if int(report.get("threshold_number") or 0) != U.THRESHOLD_ROUNDS:
        return fail(f"threshold number {report.get('threshold_number')} != {U.THRESHOLD_ROUNDS}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if E.SENTINEL not in text:
        return fail("sentinel absent from receipt")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {doc.get('state')}")
    rec_th = (
        (doc.get("tripwire_threshold") or {}).get("number")
        or doc.get("threshold_number")
    )
    if int(rec_th or 0) != U.THRESHOLD_ROUNDS:
        return fail(f"receipt threshold {rec_th} != live {U.THRESHOLD_ROUNDS}")
    rec_cast = list(doc.get("cast_that_fired") or [])
    if rec_cast != roster:
        return fail(f"receipt cast {rec_cast} != live {roster}")
    rec_seq = (doc.get("remediation_span") or {}).get("from_seq")
    if rec_seq != report.get("tripwire_seq"):
        return fail(f"receipt span from_seq {rec_seq} != live {report.get('tripwire_seq')}")

    print("SUCCESS:TST-0258-probe1 clone trip-wire fired; remediating round recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
