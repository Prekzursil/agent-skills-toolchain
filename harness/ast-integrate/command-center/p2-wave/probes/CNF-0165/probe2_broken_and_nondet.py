#!/usr/bin/env python3
"""Probe 2: known-broken diff + nondeterminism double-run + NOT-CHECKED sample."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import normalize
import replay
import safety

ART = REPO / "command-center/receipts/CNF-0165.json"


def main() -> int:
    replay.configure(REPO)
    if not ART.is_file():
        print("FAILED:CNF-0165-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0165-probe2 self-declared {doc.get('state')}")
        return 1

    good = replay.replay_claim(
        {
            "id": "good",
            "command": "printf 'CNF-0165-deterministic\\n'",
            "recorded_output": "CNF-0165-deterministic\n",
        }
    )
    bad = replay.replay_claim(
        {
            "id": "bad",
            "command": "printf 'CNF-0165-deterministic\\n'",
            "recorded_output": "CNF-0165-deterministic-ALTERED\n",
        }
    )
    if good["divergence_class"] != "match":
        print("FAILED:CNF-0165-probe2 unaltered control is not match")
        print(json.dumps(good, indent=1, default=str)[:1500])
        return 1
    if bad["divergence_class"] == "match" or bad["verdict"] == "CONFIRMED":
        print("FAILED:CNF-0165-probe2 altered recording did not fire")
        print(json.dumps(bad, indent=1, default=str)[:1500])
        return 1

    clock = replay.replay_claim(
        {
            "id": "clock",
            "command": "python3 -c \"import time; print(time.time_ns())\"",
            "recorded_output": "1111111111111111111\n",
        }
    )
    if clock["divergence_class"] != "nondeterminism":
        print("FAILED:CNF-0165-probe2 clock not classified nondeterminism")
        print(json.dumps(clock, indent=1, default=str)[:2000])
        return 1
    if not clock.get("second_run_taken"):
        print("FAILED:CNF-0165-probe2 nondeterminism without a second run")
        return 1
    if clock.get("replayed_output") == clock.get("replayed_output_run2"):
        print("FAILED:CNF-0165-probe2 two clock runs were identical; attribution unproven")
        return 1

    a, used_a = normalize.apply("ran at 2026-08-24T18:00:00Z payload=alpha")
    b, _ = normalize.apply("ran at 2026-08-24T19:00:00Z payload=alpha")
    c, _ = normalize.apply("ran at 2026-08-24T18:00:00Z payload=beta")
    if a != b or "iso8601_timestamp" not in used_a:
        print("FAILED:CNF-0165-probe2 timestamp normalizer did not absorb ISO-8601")
        return 1
    if a == c:
        print("FAILED:CNF-0165-probe2 over-normalization absorbed a content change")
        return 1

    findings = doc.get("findings") or (doc.get("report") or {}).get("findings") or []
    not_checked = [f for f in findings if f.get("verdict") == "NOT-CHECKED"]
    if len(not_checked) < 5:
        print(f"FAILED:CNF-0165-probe2 need >=5 NOT-CHECKED, got {len(not_checked)}")
        return 1
    sample = not_checked[:5]
    for row in sample:
        cmd = row.get("command") or ""
        primary = safety.classify(cmd)
        alt = safety.classify_alt(cmd)
        allowed, why = replay.allowlisted(cmd)
        missing = safety.missing_tool(cmd) if primary["ok"] and allowed else None
        genuine = (not primary["ok"]) or (not alt["ok"]) or (not allowed) or bool(missing)
        if not genuine:
            print(f"FAILED:CNF-0165-probe2 NOT-CHECKED reason not genuine: {row.get('id')}")
            print(json.dumps(row, indent=1, default=str)[:1500])
            return 1

    artifact_nondet = [
        f
        for f in findings
        if f.get("divergence_class") == "nondeterminism"
    ]
    for row in artifact_nondet:
        if not (
            row.get("second_run_taken")
            and row.get("replayed_output") != row.get("replayed_output_run2")
        ):
            print(f"FAILED:CNF-0165-probe2 artifact nondet unproven: {row.get('id')}")
            return 1

    print(
        json.dumps(
            {
                "known_broken_fired": True,
                "clean_match": True,
                "clock_class": clock["divergence_class"],
                "clock_runs_differ": True,
                "overnorm_ok": True,
                "not_checked_sampled": len(sample),
                "artifact_nondet": len(artifact_nondet),
            },
            sort_keys=True,
        )
    )
    print("overclaim_ok=False known_broken=True nondet_proven=True")
    print("SUCCESS:CNF-0165-probe2 known-broken nondeterminism NOT-CHECKED-sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
