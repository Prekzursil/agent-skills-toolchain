#!/usr/bin/env python3
"""Probe 1: re-draw the sampling frame with the recorded seed; confirm identity."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import citations as C  # noqa: E402
import harness as H  # noqa: E402
import schema_util as SU  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0065-external-benchmark-repro.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0065-probe1 {msg}")
    return 1


def counterpart_ok(claim: dict) -> bool:
    measured = claim.get("measured") or {}
    if measured.get("status") == "measured" and int(measured.get("repetitions") or 0) >= 1:
        return True
    if claim.get("verdict") == "NOT-REPRODUCIBLE":
        prereq = claim.get("missing_prerequisite") or ""
        return isinstance(prereq, str) and len(prereq) >= 8
    if claim.get("verdict") == "NOISE-DOMINATED":
        return measured.get("status") == "measured"
    return False


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    sampling = SU.sampling(doc)
    frame = C.frame()
    ids = [c["id"] for c in frame]
    if ids != list(sampling.get("frame_ids") or []):
        return fail(f"frame_ids drifted live={ids} artifact={sampling.get('frame_ids')}")
    seed = int(sampling["seed"])
    k = int(sampling["k"])
    redraw = C.sample_ids(ids, seed, k)
    recorded = list(sampling.get("sampled_ids") or [])
    print(f"seed={seed} k={k} redraw={redraw}")
    if redraw != recorded:
        return fail(f"sample redraw mismatch redraw={redraw} recorded={recorded}")
    if "CITE-FIPS-SHA256-EMPTY" not in ids:
        return fail("planted FIPS citation not in frame (extractor no-op)")
    digest = H.sha256_empty_hex()
    print(f"sha256_empty={digest}")
    if digest != H.EMPTY_SHA256:
        return fail("harness digest unstable")
    default_n = H.json_wire_size(compact=False)
    compact_n = H.json_wire_size(compact=True)
    print(f"json_default={default_n} json_compact={compact_n}")
    if compact_n != 44:
        return fail(f"compact json size {compact_n} != cited 44")
    if default_n == 44:
        return fail("default dumps already 44 bytes; undisclosed-conditions control collapsed")
    claims = SU.claims(doc)
    if len(claims) < 3:
        return fail("too few claims")
    missing = [c["id"] for c in claims if not counterpart_ok(c)]
    if missing:
        return fail(f"no counterpart: {missing}")
    aider = next((c for c in claims if c["id"] == "CITE-RES-0028-AIDER-TRADEOFF"), None)
    if aider is None:
        return fail("live RES-0028 citation dropped from sample")
    if aider.get("verdict") != "NOT-REPRODUCIBLE":
        return fail("RES-0028 must be NOT-REPRODUCIBLE while the extract is absent")
    if not (aider.get("missing_prerequisite") or "").strip():
        return fail("RES-0028 missing_prerequisite empty")
    print("redraw_identical=True planted_detected=True counterparts_ok=True")
    print("SUCCESS:CNF-0065-probe1 sample redraw identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
