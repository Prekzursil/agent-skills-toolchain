#!/usr/bin/env python3
"""Probe 1: re-draw the sampling frame with the recorded seed.

The reviewer is given the frame and the seed, re-draws, and must obtain the
identical ordered sample. A different seed must not.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sample as S  # noqa: E402
import validate as V  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0020-flake-frequency.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0020-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    payload = V.flake_payload(doc)
    seed = payload.get("seed")
    if seed != S.SEED:
        return fail(f"seed {seed!r} != {S.SEED}")
    live = S.draw_sample(int(seed))
    recorded = list(payload.get("sample") or [])
    print(f"seed={seed}")
    print(f"redraw={live}")
    print(f"recorded={recorded}")
    if live != recorded:
        return fail("sample redraw mismatch")
    live_ids = S.measured_ids(int(seed))
    rec_ids = list(payload.get("measured_ids") or [])
    if live_ids != rec_ids:
        return fail("measured_ids redraw mismatch")
    frame_sha = hashlib.sha256(S.frame_canonical().encode("utf-8")).hexdigest()
    if frame_sha != payload.get("sampling_frame_sha256"):
        return fail("sampling_frame sha256 mismatch")
    alt = S.draw_sample(int(seed) + 1)
    print(f"alt_seed_sample={alt}")
    if alt == live:
        return fail("seed+1 produced the same sample; seed is inert")
    both = payload.get("seed_both_states") or {}
    if both.get("alt_sample") != alt:
        return fail("artifact alt_sample does not match live seed+1 draw")
    if S.ALWAYS_INCLUDE_INTERMITTENT not in live:
        return fail("calibrated intermittent control missing from sample")
    if S.ALWAYS_INCLUDE_DETERMINISTIC not in live_ids:
        return fail("claimed-deterministic control missing from measured_ids")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0020" not in text:
        return fail("sentinel-absent")
    print("SUCCESS:CNF-0020-probe1 sample redraw identical; alt seed differs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
