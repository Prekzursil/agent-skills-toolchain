#!/usr/bin/env python3
"""Probe 2: determinism + independent replay from the receipt alone."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import bench as B  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0400.json"
SCHEMA = REPO / "command-center/schema/benchmark-result.schema.json"


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0400-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = S.domain(doc)
    replay = payload.get("replay") or {}
    caps = replay.get("capabilities")
    corpus = replay.get("corpus")
    k = int(replay.get("k") or 0)
    threshold = float(replay.get("threshold") or 0)
    if not caps or not corpus or k < 1:
        print("FAILED:IMP-0400-probe2 receipt is not replayable alone")
        return 1

    a = B.replay_from_receipt_payload(caps, corpus, k, threshold)
    b = B.replay_from_receipt_payload(caps, corpus, k, threshold)
    diff = B.max_metric_diff(a, b)
    if diff > float(payload["determinism"]["tolerance"]):
        print(f"FAILED:IMP-0400-probe2 two replays differ {diff}")
        return 1
    if abs(B.max_metric_diff({"metrics": payload["metrics"]}, a)) > B.DETERMINISM_TOLERANCE:
        print("FAILED:IMP-0400-probe2 replay disagrees with receipt metrics")
        return 1
    if (
        a["baseline_capture"]["snapshot_sha256"]
        != payload["baseline_capture"]["snapshot_sha256"]
    ):
        print("FAILED:IMP-0400-probe2 replay snapshot sha mismatch")
        return 1
    if a["anti_reconstruct"]["matches_captured_live"]:
        print("FAILED:IMP-0400-probe2 router reconstruction matched live")
        return 1

    rows = payload["paired_rows"]
    rec_p = mean([float(r["router_precision"]) for r in rows])
    live_p = mean([float(r["live_precision"]) for r in rows])
    if abs(rec_p - payload["metrics"]["router"]["precision_at_k"]) > 1e-12:
        print("FAILED:IMP-0400-probe2 paired_rows router precision != metrics")
        return 1
    if abs(live_p - payload["metrics"]["live"]["precision_at_k"]) > 1e-12:
        print("FAILED:IMP-0400-probe2 paired_rows live precision != metrics")
        return 1

    offered: set[str] = set()
    for r in rows:
        offered.update(r.get("router") or [])
    breadth = len(offered) / float(payload["corpus"]["capability_n"])
    if abs(breadth - payload["metrics"]["router"]["breadth"]) > 1e-12:
        print("FAILED:IMP-0400-probe2 breadth from rows != metrics")
        return 1

    mutated = copy.deepcopy(corpus)
    mutated[0]["gold"] = ["___not_a_real_capability___"]
    mut = B.replay_from_receipt_payload(caps, mutated, k, threshold)
    if abs(B.max_metric_diff(a, mut)) <= B.DETERMINISM_TOLERANCE:
        print("FAILED:IMP-0400-probe2 gold mutation was silent")
        return 1

    if not SCHEMA.is_file():
        print("FAILED:IMP-0400-probe2 schema missing")
        return 1
    for g in ({}, {"passing_tests": 999999}, {"blob": "x" * 2000}):
        if not S.iter_errors(g):
            print("FAILED:IMP-0400-probe2 schema accepted garbage")
            return 1
    replay_errs = S.error_messages(doc)
    if replay_errs:
        print("FAILED:IMP-0400-probe2 receipt failed schema on replay", replay_errs[0])
        return 1

    if payload.get("pinned_model", {}).get("id") != B.PINNED_MODEL_ID:
        print("FAILED:IMP-0400-probe2 pinned model id drift")
        return 1

    print(
        f"determinism_ok=True max_abs_diff={diff} "
        f"replay_match=True mutation_shifts=True "
        f"tolerance={payload['determinism']['tolerance']}"
    )
    print("SUCCESS:IMP-0400-probe2 determinism receipt-replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
