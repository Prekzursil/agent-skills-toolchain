#!/usr/bin/env python3
"""Probe 2: third-party re-derivation + shared completion predicate.

Does not import gate.py. Recomputes the seven-condition vector from the
CertificationRecord's cited packets via recount.py (bitmask AND), then
applies the twelve-condition program completion predicate to the live
record. A split between sequential-AND and bitmask-AND is a defect, not a
vote. Exit code of this process is not success by itself; the reducer must
report overall PASS.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import predicate as Pred  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0118-certification-gate.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0118-probe2 {msg}")
    return 1


def digest_packet(packet: dict) -> str:
    raw = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    if not ART.is_file():
        return fail("certification record absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0118" not in text or doc.get("sentinel") != "SUCCESS:WFA-0118":
        return fail("sentinel-absent")
    if doc.get("record_type") != "CertificationRecord":
        return fail("record_type mismatch")

    cited = doc.get("cited_evidence") or []
    if len(cited) < 9:
        return fail(f"cited_evidence too small {len(cited)}")

    featured = None
    live_neg = []
    for item in cited:
        packet = item.get("packet")
        if not isinstance(packet, dict):
            return fail(f"cited {item.get('id')} missing packet")
        live = digest_packet(packet)
        if live != str(item.get("sha256") or ""):
            return fail(f"hash mismatch {item.get('id')}")
        rec = R.recount(packet)
        role = str(item.get("role") or "")
        print(
            f"recount id={item.get('id')} role={role} certified={rec['certified']} "
            f"verdict={rec['verdict']} mask={rec['mask']}"
        )
        if role == "featured":
            featured = rec
            if rec["verdict"] != str(item.get("expected_verdict") or "CERTIFIED"):
                return fail("featured recount/expected split")
        elif role == "negative":
            if rec["certified"]:
                return fail(f"negative {item.get('id')} certified by bitmask")
            live_neg.append(str(item.get("removed_condition") or item.get("id")))
        elif role == "complement":
            if not rec["certified"]:
                return fail("complement packet not certified by bitmask")
        elif role == "inconclusive":
            if rec["verdict"] != "INCONCLUSIVE":
                return fail(f"inconclusive packet verdict={rec['verdict']}")

    if featured is None or not featured["certified"]:
        return fail("featured packet not independently certified")
    if doc.get("certified") is not True:
        return fail("artifact certified flag disagrees with recount")
    art_failed = [c["id"] for c in (doc.get("conditions") or []) if c.get("result") != "PASS"]
    if art_failed != featured["failed"]:
        return fail(f"condition split artifact={art_failed} recount={featured['failed']}")

    art_neg = [n.get("removed_condition") for n in (doc.get("negative_controls") or [])]
    if live_neg != art_neg:
        return fail(f"negative set split live={live_neg} artifact={art_neg}")
    if live_neg != list(R.CONDITION_BITS):
        return fail(f"negative set != seven conditions {live_neg}")

    pred = Pred.evaluate_certification_record(ART, repo=REPO)
    print(
        json.dumps(
            {
                "probe": "probe2-independent-rederive",
                "unit_id": "WFA-0118",
                "featured_mask": featured["mask"],
                "featured_certified": featured["certified"],
                "negatives": live_neg,
                "predicate_overall": pred["overall"],
                "predicate_fail_count": pred["fail_count"],
                "predicate_conditions": [
                    {"id": r["id"], "result": r["result"], "reason": r["reason"]}
                    for r in pred["conditions"]
                ],
            },
            indent=2,
        )
    )
    if pred["overall"] != "PASS":
        return fail(f"completion predicate overall={pred['overall']} fails={pred['fail_count']}")
    if pred["exit_code"] != 0:
        return fail("predicate exit_code non-zero")
    print("SUCCESS:WFA-0118-probe2 independent bitmask recount and twelve-condition reducer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
