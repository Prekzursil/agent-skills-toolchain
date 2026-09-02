#!/usr/bin/env python3
"""Probe 2: omission STALE, TTL/advisory both-states, live corpus vs artifact.

Mechanically different from probe 1: this probe does not mutate an input byte.
It checks the default-STALE omission path, age-based decay with matching hashes,
and re-scans the live confirmation corpus.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import omission_control, planted_visibility_control, ttl_and_advisory_control  # noqa: E402
from corpus import scan_corpus  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0012-freshness-decay.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0012-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0012-probe2 self-declared {doc.get('state')}")
        return 1

    omission = omission_control()
    print(
        f"omission_pass={omission['pass']} stored={omission['stored_verdict']} "
        f"live={omission['live_verdict']}"
    )
    if not omission["pass"] or omission["live_verdict"] != "STALE":
        print("FAILED:CNF-0012-probe2 omission did not default to STALE")
        return 1

    ttl = ttl_and_advisory_control()
    rows = ttl["rows"]
    print(
        f"ttl_pass={ttl['pass']} fresh={rows['fresh']['live_verdict']} "
        f"expired={rows['expired']['live_verdict']} no_ttl={rows['no_ttl']['live_verdict']}"
    )
    if not ttl["pass"]:
        print("FAILED:CNF-0012-probe2 ttl/advisory both-states failed")
        return 1
    if rows["fresh"]["live_verdict"] == rows["expired"]["live_verdict"]:
        print("FAILED:CNF-0012-probe2 ttl comparison not evaluated")
        return 1

    live = scan_corpus(REPO, now=datetime.now(timezone.utc))
    recorded = doc.get("corpus") or {}
    print(
        f"live_corpus={live['corpus_size']} stale={live['stale_count']} "
        f"load_bearing_stale={live['load_bearing_stale_count']} "
        f"empty={live['empty_corpus']}"
    )
    for key in ("corpus_size", "stale_count", "load_bearing_stale_count"):
        if recorded.get(key) != live[key]:
            print(f"FAILED:CNF-0012-probe2 artifact {key} drift")
            return 1
    if live["empty_corpus"] and recorded.get("empty_set_is_not_a_pass") is not True:
        print("FAILED:CNF-0012-probe2 empty set read as pass")
        return 1
    if live["empty_corpus"]:
        answer = doc.get("answer") or ""
        stated = f"{live['stale_count']} of {live['corpus_size']}"
        if stated not in answer:
            print("FAILED:CNF-0012-probe2 empty corpus not stated in answer")
            return 1
        items = {i.get("id"): i for i in (doc.get("items") or []) if isinstance(i, dict)}
        corpus_item = items.get("confirmation-receipt-corpus") or {}
        if corpus_item.get("three_state") != "GENUINE_ZERO":
            print("FAILED:CNF-0012-probe2 empty corpus not GENUINE_ZERO")
            return 1
        if corpus_item.get("integrity_class") == "FOLDED-INTO-PASS":
            print("FAILED:CNF-0012-probe2 empty corpus folded into pass")
            return 1
        summary = doc.get("summary") or {}
        if summary.get("folded_into_pass") != 0:
            print("FAILED:CNF-0012-probe2 summary folded_into_pass != 0")
            return 1
    planted = planted_visibility_control(REPO, HERE / "fixtures")
    print(
        f"planted_pass={planted['pass']} labelled={planted['labelled_seen']} "
        f"unlabelled_rejected={planted['unlabelled_rejected']}"
    )
    if not planted["pass"]:
        print("FAILED:CNF-0012-probe2 planted labelled receipt not visible")
        return 1
    controls = doc.get("controls") or {}
    for key in (
        "absent_dir_not_nothing_to_check",
        "unrunnable_gate_not_silent_pass",
        "planted_unlabelled_caught",
    ):
        if controls.get(key) is not True:
            print(f"FAILED:CNF-0012-probe2 controls.{key} not true")
            return 1
    print("SUCCESS:CNF-0012-probe2 omission STALE, TTL both-states, live corpus matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
