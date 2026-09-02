#!/usr/bin/env python3
"""Probe 2: volume is absent from score inputs; small-n producers are labelled not scored."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from schema_bind import domain  # noqa: E402
from scoring import SCORE_INPUTS, load_frame, load_prereg, recompute_weights_from_raw, score_frame  # noqa: E402

UNIT = "SYN-0036"
ART = REPO / "command-center/receipts/SYN-0036.json"
VOLUME_KEYS = ("volume_bytes", "volume_tokens", "bytes", "tokens", "kilobytes")


def fail(msg: str) -> int:
    print("FAILED:%s-probe2 %s" % (UNIT, msg))
    return 1


def main() -> int:
    prereg = load_prereg()
    scored = score_frame()
    frame = load_frame()
    by_id = {r["producer_id"]: r for r in scored["producers"]}
    high = by_id["P-HIGH"]
    low = by_id["P-LOW"]
    tiny = by_id["P-TINY"]
    print(
        "P-HIGH n=%s survived=%s weight=%s volume_tokens=%s"
        % (high["n"], high["survived"], high["weight"], frame["producers"][0]["volume_tokens"])
    )
    print(
        "P-LOW n=%s survived=%s weight=%s volume_tokens=%s"
        % (low["n"], low["survived"], low["weight"], frame["producers"][1]["volume_tokens"])
    )
    print("P-TINY n=%s label=%s weight=%s" % (tiny["n"], tiny["label"], tiny["weight"]))

    if high["weight"] is None or low["weight"] is None:
        return fail("scored producers missing weights")
    if not (high["weight"] > low["weight"]):
        return fail("high-survival low-volume did not outrank high-volume low-survival")
    if frame["producers"][1]["volume_tokens"] <= frame["producers"][0]["volume_tokens"]:
        return fail("volume decoy not planted")
    if tiny["label"] != "INSUFFICIENT-N" or tiny["weight"] is not None:
        return fail("small-n producer was scored")
    if tiny["n"] >= int(prereg["min_n"]):
        return fail("P-TINY n is not below min_n")
    if any(k in SCORE_INPUTS for k in VOLUME_KEYS):
        return fail("volume key leaked into SCORE_INPUTS")
    if tuple(prereg["score_inputs"]) != SCORE_INPUTS:
        return fail("prereg score_inputs drifted")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = domain(doc)
    if payload.get("volume_excluded_from_score") is not True:
        return fail("artifact volume_excluded_from_score is not true")
    labels = {p["producer_id"]: p for p in payload["producers"]}
    if labels["P-TINY"]["label"] != "INSUFFICIENT-N" or labels["P-TINY"]["weight"] is not None:
        return fail("artifact scored P-TINY")
    if not (labels["P-HIGH"]["weight"] > labels["P-LOW"]["weight"]):
        return fail("artifact inverted P-HIGH vs P-LOW")
    raw_claims = (payload.get("raw_table") or {}).get("claims") or []
    recomputed = recompute_weights_from_raw(raw_claims, int(payload["min_n"]))
    for pid, w in recomputed.items():
        published = labels[pid]["weight"]
        if published is None and w is None:
            continue
        if published is None or w is None or abs(float(published) - float(w)) > 1e-12:
            return fail("reviewer recompute mismatch %s published=%s recomputed=%s" % (pid, published, w))
    insuff = [p for p in payload["producers"] if p["n"] < int(payload["min_n"])]
    if not insuff:
        return fail("no low-n producer labelled")
    if any(p["label"] != "INSUFFICIENT-N" or p["weight"] is not None for p in insuff):
        return fail("a low-n producer was given a weight")
    if any(k in (payload.get("score_inputs") or []) for k in VOLUME_KEYS):
        return fail("artifact score_inputs contain a volume key")

    summary = {
        "high_outranks_low_despite_volume": True,
        "pass": True,
        "probe": "probe2-volume-and-small-n",
        "reviewer_recompute_ok": True,
        "tiny_labelled_not_scored": True,
        "unit_id": UNIT,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:%s-probe2 volume ignored; small-n labelled INSUFFICIENT-N" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
