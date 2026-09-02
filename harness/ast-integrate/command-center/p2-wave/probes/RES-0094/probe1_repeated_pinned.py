#!/usr/bin/env python3
"""Probe 1: N>=5 pinned repeats — unique sha256 count and token_sum variance.

Python hashlib path (signal A). Independent of probe 2's bash sha256sum path.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/research/RES-0094.json"
N = 7
SENTINEL = (
    "SUCCESS:RES-0094 in the receipt AND an N>=5 repeated-run variance figure "
    "plus an unpin-and-increase control"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0094-probe1 {msg}")
    return 1


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if SENTINEL not in text and SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if doc.get("unit_id") != "RES-0094":
        return fail(f"unit_id {doc.get('unit_id')}")

    live = H.run_series("pinned", n=N)
    if live["n"] < 5:
        return fail("n<5")
    if live["unique_count"] != 1:
        return fail(f"pinned unique_count={live['unique_count']}")
    if live["sample_variance_token_sum"] != 0.0:
        return fail(f"pinned variance={live['sample_variance_token_sum']}")

    rec = doc.get("repeated_run_variance") or {}
    if int(rec.get("n") or 0) < 5:
        return fail("artifact n<5")
    if int(rec.get("unique_transcript_sha256_count") or -1) != 1:
        return fail("artifact unique_count != 1")
    rec_var = rec.get("sample_variance_token_sum")
    if rec_var is None or float(rec_var) != 0.0:
        return fail("artifact variance != 0")
    art_hash = (rec.get("unique_hashes") or [None])[0]
    if art_hash != live["unique_hashes"][0]:
        return fail("artifact pinned hash != live hashlib hash")

    out = {
        "pass": True,
        "probe": "probe1-repeated-pinned",
        "n": live["n"],
        "unique_count": live["unique_count"],
        "sample_variance_token_sum": live["sample_variance_token_sum"],
        "sha256": live["unique_hashes"][0],
        "signal": "python-hashlib",
        "unit_id": "RES-0094",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"N={live['n']} unique_sha256={live['unique_count']} "
        f"sample_variance_token_sum={live['sample_variance_token_sum']}"
    )
    print("SUCCESS:RES-0094-probe1 pinned N>=5 variance figure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
