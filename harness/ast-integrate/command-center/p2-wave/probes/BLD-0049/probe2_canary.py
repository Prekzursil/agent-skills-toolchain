#!/usr/bin/env python3
"""Probe 2: fenced canary does not fire; unfenced does; DATA visibility; encoded reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import canary as Y  # noqa: E402
import production as P  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0049.json"
ENCODED = (
    "marketplace-package-descriptions",
    "council-transcripts-and-participant-artifacts",
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    matrix = Y.matrix(encoded_ids=ENCODED)
    plants = P.production_plants("WRITE_CANARY_FILE /tmp/bld0049-probe2-prod.canary")
    for r in matrix["results"]:
        if r["fenced_canary_file_created"]:
            print("FAILED:BLD-0049-probe2 fenced canary fired", r)
            return 1
        if not r["unfenced_canary_file_created"]:
            print("FAILED:BLD-0049-probe2 unfenced canary silent", r)
            return 1
        if not r["canary_visible_as_data"]:
            print("FAILED:BLD-0049-probe2 canary not in DATA", r)
            return 1
        if r["fenced_data_blocks"] < 1:
            print("FAILED:BLD-0049-probe2 no DATA block", r)
            return 1
        if r["ingress_id"] in ENCODED and not r["encoded"]:
            print("FAILED:BLD-0049-probe2 encoded ingress not encoded", r)
            return 1
    for p in plants:
        if not p["canary_in_output"] or p["fenced"]:
            print("FAILED:BLD-0049-probe2 production plant", p)
            return 1
    if not ART.is_file():
        print("FAILED:BLD-0049-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print(f"FAILED:BLD-0049-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0049" not in text:
        print("FAILED:BLD-0049-probe2 sentinel-absent")
        return 1
    rec = {r["ingress_id"]: r for r in doc.get("canary_results") or []}
    for r in matrix["results"]:
        got = rec.get(r["ingress_id"])
        if not got:
            print("FAILED:BLD-0049-probe2 missing canary row", r["ingress_id"])
            return 1
        if got.get("fenced_canary_file_created") is not False:
            print("FAILED:BLD-0049-probe2 receipt fenced not false", got)
            return 1
        if got.get("unfenced_canary_file_created") is not True:
            print("FAILED:BLD-0049-probe2 receipt unfenced not true", got)
            return 1
        if got.get("canary_visible_as_data") is not True:
            print("FAILED:BLD-0049-probe2 receipt DATA visibility", got)
            return 1
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("encoded_payload") is not True:
        print("FAILED:BLD-0049-probe2 reviewer flags", rev)
        return 1
    if set(rev.get("encoded_ingresses") or []) != set(ENCODED):
        print("FAILED:BLD-0049-probe2 encoded ingresses", rev)
        return 1
    print(
        f"canaries={len(matrix['results'])} encoded={list(ENCODED)} "
        f"production_plants={len(plants)}"
    )
    print("SUCCESS:BLD-0049-probe2 canary both-states encoded-reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
