#!/usr/bin/env python3
"""Probe 2: two independent parsers agree within 10%; live re-count matches artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import measure  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0035.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0035-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = measure()
    tp = live["two_pass"]
    if tp["relative_delta"] > 0.10:
        return fail(
            f"two-pass delta {tp['relative_delta']} exceeds 10% "
            f"(a={tp['pass_a_count']} b={tp['pass_b_count']})"
        )
    if not tp["within_10_percent"]:
        return fail("within_10_percent flag is false")
    art_tp = doc.get("two_pass") or {}
    if art_tp.get("pass_a_count") != tp["pass_a_count"] or art_tp.get("pass_b_count") != tp["pass_b_count"]:
        return fail("artifact two-pass counts drifted from live re-count")
    if live["definition_sha256"] != (doc.get("definition") or {}).get("sha256"):
        return fail("live definition hash drifted from artifact")

    by_live = {v["vendor_id"]: v["count"] for v in live["vendors"]}
    for row in doc.get("per_vendor_counts") or []:
        vid = row["vendor_id"]
        if by_live.get(vid) != row["count"]:
            return fail(f"vendor {vid} count drifted live={by_live.get(vid)} art={row['count']}")

    claude = next(v for v in live["vendors"] if v["vendor_id"] == "anthropic-claude-code")
    for item in claude["items"]:
        if not item.get("published_at"):
            return fail("claude counted item missing published_at")

    payload = {
        "probe": "probe2-two-pass-agreement",
        "unit_id": "RES-0035",
        "pass_a_count": tp["pass_a_count"],
        "pass_b_count": tp["pass_b_count"],
        "relative_delta": tp["relative_delta"],
        "within_10_percent": True,
        "live_matches_artifact": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0035-probe2 two-pass counts agree within 10%; "
        "live re-count matches artifact"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
