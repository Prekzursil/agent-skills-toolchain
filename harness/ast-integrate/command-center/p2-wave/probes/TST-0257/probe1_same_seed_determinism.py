#!/usr/bin/env python3
"""Probe 1: same-seed byte identity and different-seed divergence.

Re-runs the simulator live. If the receipt exists, its hashes must match
this live pair. A constant transcript or an unwired seed fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0257.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0257-probe1 {msg}")
    return 1


def main() -> int:
    live = S.live()
    if not live.get("same_seed_identical"):
        return fail(
            f"same-seed transcripts differ "
            f"{live.get('sha256_seed_a_run1')} vs {live.get('sha256_seed_a_run2')}"
        )
    if not live.get("seed_wired"):
        return fail(
            "different seed did not change transcript body "
            f"a={live.get('body_sha256_seed_a')} b={live.get('body_sha256_seed_b')}"
        )
    if live.get("sha256_seed_a_run1") == live.get("sha256_seed_b"):
        return fail("full hashes collided across seeds")
    if live.get("model_calls") != 0:
        return fail(f"model_calls={live.get('model_calls')} want 0")

    print(
        f"same_seed={live['sha256_seed_a_run1']} "
        f"seed_b={live['sha256_seed_b']} "
        f"body_a={live['body_sha256_seed_a']} body_b={live['body_sha256_seed_b']}"
    )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("determinism") or {}
        if rec.get("sha256_seed_a_run1") != live["sha256_seed_a_run1"]:
            return fail("receipt sha256_seed_a_run1 != live")
        if rec.get("sha256_seed_a_run2") != live["sha256_seed_a_run2"]:
            return fail("receipt sha256_seed_a_run2 != live")
        if rec.get("sha256_seed_b") != live["sha256_seed_b"]:
            return fail("receipt sha256_seed_b != live")
        if rec.get("body_sha256_seed_a") != live["body_sha256_seed_a"]:
            return fail("receipt body hash a != live")
        if rec.get("body_sha256_seed_b") != live["body_sha256_seed_b"]:
            return fail("receipt body hash b != live")
        print("receipt hashes match live pair")

    print("SUCCESS:TST-0257-probe1 same-seed identity and different-seed divergence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
