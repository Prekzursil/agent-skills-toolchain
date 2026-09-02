#!/usr/bin/env python3
"""Probe 2: single-seed perturbation diverges; cached transcript is rejected.

Independent recount: event-index fingerprint (NUL-joined fields), not JSONL sha256.
Re-tabulates measure() and, when present, the catalog artifact's reported hashes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cached import CachedTranscriptRuntime, perturbation_verdict  # noqa: E402
from harness import (  # noqa: E402
    digest_events,
    event_index_fingerprint,
    first_divergence,
    measure,
    perturb_seeds,
    transcript_bytes,
    uninterrupted,
)
from scenario import DEFAULT_SEEDS, SEED_NAMES  # noqa: E402

ARTIFACT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0122-pause-resume-and-deterministic-replay-simulation.md"
)


def main() -> int:
    doc = measure()
    base = uninterrupted(DEFAULT_SEEDS)
    base_raw = transcript_bytes(base.events)
    base_sha = digest_events(base.events)
    base_fp = event_index_fingerprint(base.events)

    if not doc["all_seeds_load_bearing"]:
        print("FAILED:CNL-0122-probe2 a captured seed did not move the transcript")
        return 1

    for row in doc["perturbation"]:
        name = row["seed"]
        live = uninterrupted(perturb_seeds(DEFAULT_SEEDS, name))
        live_sha = digest_events(live.events)
        live_fp = event_index_fingerprint(live.events)
        div = first_divergence(base.events, live.events)
        print(
            f"perturb {name} sha256={live_sha} fingerprint={live_fp} "
            f"diverged={live_sha != base_sha} fp_diverged={live_fp != base_fp} "
            f"first_index={div.get('index')} first_kind={div.get('kind')}"
        )
        if live_sha == base_sha:
            print(f"FAILED:CNL-0122-probe2 {name} is decorative (JSONL sha256)")
            return 1
        # Fingerprint omits utterance text on purpose so it is a different
        # mechanism from JSONL sha256. sampling_seed must still move sha256;
        # the other three seeds must also move the index fingerprint.
        if name != "sampling_seed" and live_fp == base_fp:
            print(f"FAILED:CNL-0122-probe2 {name} did not move event-index fingerprint")
            return 1
        if name == "sampling_seed" and live_fp != base_fp:
            print("FAILED:CNL-0122-probe2 sampling_seed moved fingerprint; mechanisms collapsed")
            return 1
        if live_sha != row["sha256"]:
            print(f"FAILED:CNL-0122-probe2 {name} recount disagrees with measure()")
            return 1
        if div.get("index") is None:
            print(f"FAILED:CNL-0122-probe2 {name} hashes differ but events compare equal")
            return 1

    real = perturbation_verdict(
        base_raw,
        transcript_bytes(
            uninterrupted(perturb_seeds(DEFAULT_SEEDS, "sampling_seed")).events
        ),
    )
    cached_rt = CachedTranscriptRuntime(base_raw)
    cached = perturbation_verdict(
        cached_rt.transcript(DEFAULT_SEEDS),
        cached_rt.transcript(perturb_seeds(DEFAULT_SEEDS, "sampling_seed")),
    )
    print(
        f"negative_control real={real['verdict']}/{real['why']} "
        f"cached={cached['verdict']}/{cached['why']} cached_hits={cached_rt.hits}"
    )
    if real["verdict"] != "ACCEPT":
        print("FAILED:CNL-0122-probe2 real runtime did not diverge on seed kill")
        return 1
    if cached["verdict"] != "REJECT" or cached["why"] != "frozen-or-cached-transcript":
        print("FAILED:CNL-0122-probe2 cached runtime was not rejected")
        return 1
    if cached_rt.hits != 2:
        print("FAILED:CNL-0122-probe2 cached runtime was not invoked twice")
        return 1

    # Verbatim record of what the check does on the state it is meant to reject.
    print(
        "negative_control_on_rejected_state="
        "CachedTranscriptRuntime ignores the perturbed seed and returns the "
        f"first transcript; check reports verdict={cached['verdict']} "
        f"why={cached['why']} (identical-seed replay alone would have passed it)"
    )
    print(
        "negative_control_on_accepted_state="
        f"real CouncilSim sampling_seed xor; check reports verdict={real['verdict']} "
        f"why={real['why']}"
    )

    if ARTIFACT.is_file() and ARTIFACT.stat().st_size > 0:
        reported = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        results = reported.get("results") or {}
        reported_sha = (
            (results.get("uninterrupted") or {}).get("sha256")
            or results.get("uninterrupted_sha256")
        )
        if reported_sha and reported_sha != base_sha:
            print(
                f"FAILED:CNL-0122-probe2 artifact sha256 {reported_sha} "
                f"!= live {base_sha}"
            )
            return 1
        pert = results.get("perturbation") or []
        if pert:
            live_map = {r["seed"]: r["sha256"] for r in doc["perturbation"]}
            for row in pert:
                seed = row.get("seed")
                if seed in live_map and row.get("sha256") != live_map[seed]:
                    print(f"FAILED:CNL-0122-probe2 artifact perturbation mismatch {seed}")
                    return 1
        print(f"artifact_recount_ok sha256={base_sha}")

    print(
        json.dumps(
            {
                "all_seeds_load_bearing": True,
                "cached_rejected": True,
                "real_accepted": True,
                "uninterrupted_sha256": base_sha,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0122-probe2 seed-perturbation and cached-transcript control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
