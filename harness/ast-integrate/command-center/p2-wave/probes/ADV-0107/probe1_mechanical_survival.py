#!/usr/bin/env python3
"""Probe 1: mechanical counts and survival rates on both sides of every boundary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harvest  # noqa: E402

UNIT = "ADV-0107"


def main() -> int:
    m = harvest.measure()
    mention = m["mention"]
    payload = {
        "probe": "probe1-mechanical-survival",
        "unit_id": UNIT,
        "mention_control": {
            "pass": mention["pass"],
            "naive": mention["naive"],
            "use": mention["use"],
            "naive_strictly_exceeds_use": mention["naive_strictly_exceeds_use"],
            "use_matches_oracle": mention["use_matches_oracle"],
        },
        "boundaries": [
            {
                "id": b["id"],
                "src_use": b["src_use"],
                "dst_use": b["dst_use"],
                "survival": b["survival"],
                "matches_oracle": b["matches_oracle"],
            }
            for b in m["boundaries"]
        ],
        "live": {
            "pair_count": m["live"]["pair_count"],
            "digest_named_file_count": m["live"]["digest_named_file_count"],
        },
        "pass": m["pass_mechanical"],
    }
    print(json.dumps(payload, sort_keys=True))
    if not mention["pass"]:
        print(f"FAILED:{UNIT}-probe1 use-vs-mention control failed")
        print(json.dumps(mention, sort_keys=True)[:2000])
        return 1
    if not m["fixture_oracle_ok"]:
        print(f"FAILED:{UNIT}-probe1 fixture counts missed oracle")
        return 1
    rates = m["boundaries"][0]["survival"]
    for k in ("unverified", "band", "file_line", "url"):
        if rates[k]["survival_rate"] is None:
            print(f"FAILED:{UNIT}-probe1 missing rate for {k}")
            return 1
    if rates["url"]["survival_rate"] != 0.0:
        print(f"FAILED:{UNIT}-probe1 expected URL total loss, got {rates['url']}")
        return 1
    print(
        "mention_ok=True boundaries="
        + str(len(m["boundaries"]))
        + " url_survival="
        + str(rates["url"]["survival_rate"])
    )
    print(f"SUCCESS:{UNIT}-probe1 mechanical survival rates per boundary and class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
