#!/usr/bin/env python3
"""Probe 2: semantic survival on a sample — mechanically different from counts.

A digest that drops the literal token but keeps the qualification is not a loss.
A digest that drops both the token and the qualification is a true loss.
Only reading sampled pairs distinguishes the two.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harvest  # noqa: E402
from semantic import compare_pair  # noqa: E402

UNIT = "ADV-0107"


def main() -> int:
    m = harvest.measure()
    raw = (HERE / "fixtures" / "raw_round.md").read_text(encoding="utf-8")
    digest = (HERE / "fixtures" / "digest_round.md").read_text(encoding="utf-8")
    dod = (HERE / "fixtures" / "digest_of_digest.md").read_text(encoding="utf-8")
    pair1 = compare_pair(raw, digest)
    pair2 = compare_pair(digest, dod)

    keep_u3 = any(
        r.get("claim_id") == "C-U3" and r["kind"] == "unverified" and r["semantic_keep"]
        for r in pair1["rows"]
        if not r["mechanical"]
    )
    keep_queue = any(
        r["kind"] == "file_line"
        and "queue.py:100" in str(r.get("value"))
        and r["semantic_keep"]
        for r in pair1["rows"]
        if not r["mechanical"]
    )
    lose_u4 = any(
        r.get("claim_id") == "C-U4" and r["kind"] == "unverified" and r["true_loss"]
        for r in pair1["rows"]
    )
    lose_urls = [
        r for r in pair1["rows"] if r["kind"] == "url" and r["true_loss"]
    ]
    # Control: token-present pair must not be labelled true_loss.
    u1_ok = any(
        r.get("claim_id") == "C-U1"
        and r["kind"] == "unverified"
        and r["mechanical"]
        and not r["true_loss"]
        for r in pair1["rows"]
    )

    payload = {
        "probe": "probe2-semantic-sample",
        "unit_id": UNIT,
        "raw_to_digest": {
            "mechanical_losses": pair1["mechanical_losses"],
            "semantic_survivors_among_mech_loss": pair1[
                "semantic_survivors_among_mech_loss"
            ],
            "true_losses": pair1["true_losses"],
            "planted_unverified_kept_as_prose": keep_u3,
            "planted_file_line_kept_as_prose": keep_queue,
            "planted_unverified_true_loss": lose_u4,
            "url_true_losses": len(lose_urls),
            "token_present_not_loss": u1_ok,
        },
        "digest_to_dod": {
            "mechanical_losses": pair2["mechanical_losses"],
            "semantic_survivors_among_mech_loss": pair2[
                "semantic_survivors_among_mech_loss"
            ],
            "true_losses": pair2["true_losses"],
        },
        "pass": bool(
            keep_u3 and keep_queue and lose_u4 and len(lose_urls) == 3 and u1_ok
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print(f"FAILED:{UNIT}-probe2 semantic sample did not separate keep vs loss")
        print(json.dumps(payload, indent=2)[:3000])
        return 1
    if not m["pass_semantic"]:
        print(f"FAILED:{UNIT}-probe2 harvest semantic flags")
        return 1
    print(
        f"keep_u3={keep_u3} keep_queue={keep_queue} lose_u4={lose_u4} "
        f"url_true_losses={len(lose_urls)}"
    )
    print(f"SUCCESS:{UNIT}-probe2 semantic sample distinguishes token-drop from loss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
