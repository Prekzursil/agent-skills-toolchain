#!/usr/bin/env python3
"""Restore RES-0103 reviewer block (envelope rewrite made notes a string).

Rebuilds doc["reviewer"] exactly as the unit's emit.py does, from a live
rerun of the unit-local reviewer.review(doc).
"""
import json
import sys
from pathlib import Path

SHARD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARD_DIR))
import _shard07_lib as L

UNIT_DIR = L.REPO / "command-center/p2-wave/probes/RES-0103"
sys.path.insert(0, str(UNIT_DIR))
import reviewer as R  # noqa: E402

ART = "command-center/research/RES-0103.json"
doc = L.load(ART)

rev = R.review(doc)
print(json.dumps({k: v for k, v in rev.items() if k != "added_failure_mode"}, indent=1, sort_keys=True))
if rev["verdict"] != "PASS":
    raise SystemExit("live reviewer rerun did not PASS; refusing to write")

doc["reviewer"] = {
    "reviewer_id": rev["reviewer_id"],
    "independent": True,
    "verdict": rev["verdict"],
    "scope_not_agreement": True,
    "defaults_to_refuted": True,
    "notes": {
        "inverted_ratio_moves_threshold": rev["inverted_ratio_moves_threshold"],
        "abstention_strictly_worse_on_inverted": rev[
            "abstention_strictly_worse_on_inverted"
        ],
        "e3_promoted": rev["e3_promoted"],
        "added_failure_mode": rev["added_failure_mode"],
    },
}

L.save(ART, doc)
L.refresh_manifest("RES-0103", [ART])
print("RES-0103 reviewer block restored from live unit reviewer rerun")
