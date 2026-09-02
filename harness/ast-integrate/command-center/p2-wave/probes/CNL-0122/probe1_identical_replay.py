#!/usr/bin/env python3
"""Probe 1: identical-seed pause/resume and snapshot replay are byte-identical."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    digest_events,
    event_index_fingerprint,
    measure,
    pause_resume,
    uninterrupted,
)
from scenario import DEFAULT_SEEDS, PAUSE_ROUNDS  # noqa: E402


def main() -> int:
    doc = measure()
    base = uninterrupted(DEFAULT_SEEDS)
    base_sha = digest_events(base.events)
    base_fp = event_index_fingerprint(base.events)
    print(
        f"uninterrupted sha256={base_sha} fingerprint={base_fp} "
        f"events={len(base.events)} bytes={doc['uninterrupted']['bytes']}"
    )
    if base_sha != doc["uninterrupted"]["sha256"]:
        print("FAILED:CNL-0122-probe1 measure() sha256 disagrees with live run")
        return 1
    if base_fp != doc["uninterrupted"]["fingerprint"]:
        print("FAILED:CNL-0122-probe1 measure() fingerprint disagrees with live run")
        return 1

    for row in doc["pause_resume"]:
        k = row["pause_after_round"]
        print(
            f"pause_after_round={k} resume_sha256={row['resume_sha256']} "
            f"replay_sha256={row['replay_sha256']} "
            f"identical={row['identical_to_uninterrupted']} "
            f"replay_identical={row['replay_identical']} "
            f"snapshot_events={row['snapshot_event_count']} "
            f"snapshot_next_round={row['snapshot_next_round']}"
        )
        if not row["identical_to_uninterrupted"] or not row["replay_identical"]:
            print(f"FAILED:CNL-0122-probe1 round {k} resume/replay diverged")
            return 1
        if row["resume_sha256"] != base_sha or row["replay_sha256"] != base_sha:
            print(f"FAILED:CNL-0122-probe1 round {k} hash mismatch vs uninterrupted")
            return 1
        live = pause_resume(k, DEFAULT_SEEDS)
        if digest_events(live.events) != base_sha:
            print(f"FAILED:CNL-0122-probe1 live pause_resume({k}) diverged")
            return 1
        if event_index_fingerprint(live.events) != base_fp:
            print(f"FAILED:CNL-0122-probe1 live fingerprint at round {k} diverged")
            return 1

    missing = set(PAUSE_ROUNDS) - {r["pause_after_round"] for r in doc["pause_resume"]}
    if missing:
        print(f"FAILED:CNL-0122-probe1 unpopulated pause rounds {sorted(missing)}")
        return 1
    if not doc["identical_seed_byte_identical"]:
        print("FAILED:CNL-0122-probe1 identical_seed_byte_identical is false")
        return 1

    print(json.dumps({"identical_seed_byte_identical": True, "sha256": base_sha}, sort_keys=True))
    print("SUCCESS:CNL-0122-probe1 identical-seed pause/resume/replay byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
