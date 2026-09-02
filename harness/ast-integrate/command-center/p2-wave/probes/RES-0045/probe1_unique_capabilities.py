#!/usr/bin/env python3
"""Probe 1: per-protocol unique capabilities recomputed from snapshot bytes.

Catalog test: name at least one unique capability per protocol, or NONE-FOUND.
Rehashes captured rails. Does not evaluate the adopt/decline recommendation
(that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402


def main() -> int:
    if not C.ART.is_file():
        print("FAILED:RES-0045-probe1 artifact missing")
        return 1
    doc = C.load_art()
    live = C.unique_from_snapshots()
    errs = C.validate_unique_caps(doc)
    summary = {
        proto: {
            "none_found": live[proto]["none_found"],
            "ids": [c["id"] for c in live[proto]["capabilities"]],
        }
        for proto in ("mcp", "a2a", "agent_connect")
    }
    print(
        json.dumps(
            {"errors": errs, "live_unique": summary, "n_claims": len(doc.get("claims") or [])},
            indent=2,
            sort_keys=True,
        )
    )
    if errs:
        print("FAILED:RES-0045-probe1 " + "; ".join(errs[:8]))
        return 1
    print(
        "SUCCESS:RES-0045-probe1 unique-capabilities "
        f"mcp={len(summary['mcp']['ids'])} a2a={len(summary['a2a']['ids'])} "
        f"agent_connect={len(summary['agent_connect']['ids'])} two-rails"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
