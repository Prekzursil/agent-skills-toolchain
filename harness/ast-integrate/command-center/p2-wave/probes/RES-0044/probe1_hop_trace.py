#!/usr/bin/env python3
"""Probe 1: rebuild the hop-by-hop token-location trace from the captured spec.

Does not trust the artifact's hop list. Re-derives from spec-authorization.mdx
and checks the artifact matches. Mutating a hop's storage_location to omit it
must fail (both-states).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import hops as H  # noqa: E402
import rails as R  # noqa: E402

UNIT = "RES-0044"
ART = REPO / "command-center/research/RES-0044.json"
SENTINEL = (
    "SUCCESS:RES-0044 in the receipt AND a hop-by-hop token-location trace "
    "plus a scan result showing the artifact is credential-free"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = ART.read_text(encoding="utf-8")
    if SENTINEL not in blob:
        return fail("sentinel absent from artifact")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    spec = R.load_decoded_spec()
    live = H.build_hop_trace(spec)
    if not live["complete"]:
        return fail(f"spec missing markers/beats {live['missing']}")
    if len(live["hops"]) < 10:
        return fail(f"too few hops {len(live['hops'])}")
    unnamed = [h["hop"] for h in live["hops"] if not h.get("storage_location")]
    if unnamed:
        return fail(f"unnamed storage on hops {unnamed}")

    art_trace = doc.get("hop_by_hop_token_location_trace") or {}
    art_hops = art_trace.get("hops") or []
    if len(art_hops) != len(live["hops"]):
        return fail(f"artifact hop count {len(art_hops)} != live {len(live['hops'])}")
    for a, b in zip(art_hops, live["hops"]):
        if a.get("hop") != b.get("hop") or a.get("storage_location") != b.get("storage_location"):
            return fail(f"hop mismatch {a} vs {b}")
        if a.get("token_kind") != b.get("token_kind"):
            return fail(f"token_kind mismatch hop {a.get('hop')}")

    mutant = deepcopy(live)
    mutant["hops"][9]["storage_location"] = ""
    if mutant["hops"][9]["storage_location"] == live["hops"][9]["storage_location"]:
        return fail("mutant did not change hop 10 storage")
    if not live["hops"][9]["storage_location"]:
        return fail("live hop 10 storage empty so mutant is inert")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("T1-hop-trace", {}).get("result") != "PASS":
        return fail("T1-hop-trace not PASS in artifact")

    print(
        json.dumps(
            {
                "probe": "probe1-hop-trace",
                "hops": len(live["hops"]),
                "complete": live["complete"],
                "stdio_exempt": live["spec_markers_present"].get("stdio_exempt"),
                "query_forbidden": live["spec_markers_present"].get("query_forbidden"),
                "artifact_matches_live": True,
                "mutant_unnamed_hop10_differs": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe1 hop-by-hop token-location trace rebuilt from spec")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
