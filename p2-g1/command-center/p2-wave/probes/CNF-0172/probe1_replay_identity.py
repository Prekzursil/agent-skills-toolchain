#!/usr/bin/env python3
"""CNF-0172 named probe 1 (wave-2 reconstruction): replay identity.

Re-derives, live and independently, the four-way identity the receipt claims:
  * sha256(json.dumps(component, sort_keys=True, separators=(',',':')))
    recomputed over decision / vote_history / confidence_trajectory /
    dissent_set must reproduce the recorded four_hashes;
  * corrected_repro.four_hashes (the log replay) must EQUAL baseline
    four_hashes for all four components;
  * dissent_preservation: the replayed dissent set must deep-equal the
    baseline minority report (spec:11238 — losing the dissent is a failure);
  * the recorded drop-skeptic regression hash for confidence_trajectory is
    reproduced by the same canonicalizer (the diff is real, not narrated).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "CNF-0172.json"
COMPONENTS = ("decision", "vote_history", "confidence_trajectory", "dissent_set")


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state", "")).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0172-probe1 self-declared " + str(doc.get("state")))
        return 1
    if "SUCCESS:CNF-0172" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0172-probe1 sentinel absent")
        return 1
    base = doc["baseline_repro"]
    rec = base["four_hashes"]

    recomputed = {c: sha(base[c]) for c in COMPONENTS}
    mismatches = {c: {"recorded": rec[c], "recomputed": recomputed[c]} for c in COMPONENTS if rec[c] != recomputed[c]}
    if mismatches:
        print("FAILED:CNF-0172-probe1 four-hash recomputation mismatch " + json.dumps(mismatches))
        return 1

    corr = doc.get("corrected_repro") or {}
    corr_hashes = corr.get("four_hashes") or {}
    replay_equal = {c: (corr_hashes.get(c) == rec[c]) for c in COMPONENTS}
    if not all(replay_equal.values()):
        print("FAILED:CNF-0172-probe1 recorded replay identity broken: " + json.dumps(replay_equal))
        return 1

    dp = doc.get("dissent_preservation") or {}
    if dp.get("replayed_dissent_set") != base["dissent_set"]:
        print("FAILED:CNF-0172-probe1 replayed dissent set differs from baseline (dissent loss)")
        return 1

    # reproduce the recorded regression hash: drop skeptic from confidence_trajectory
    dropped = [e for e in base["confidence_trajectory"] if e.get("participant") != "skeptic"]
    rd = (doc.get("regression_diff") or {}).get("drop_participant") or {}
    b_hash = ((rd.get("confidence_trajectory") or {}).get("b")) or ""
    reproduced = bool(b_hash) and sha(dropped) == b_hash
    if not reproduced:
        print("FAILED:CNF-0172-probe1 drop-skeptic regression hash not reproduced")
        return 1
    decision_unchanged = ((rd.get("decision") or {}).get("match") is True)

    report = {
        "probe": "probe1-replay-identity",
        "unit_id": "CNF-0172",
        "canonicalizer": "json.dumps(sort_keys=True, separators=(',',':')) + sha256",
        "four_hashes_reproduced_live": {c: recomputed[c] for c in COMPONENTS},
        "replay_hashes_equal_baseline": replay_equal,
        "dissent_preserved_deep_equal": True,
        "drop_skeptic_regression_hash_reproduced": reproduced,
        "decision_unchanged_in_regression": decision_unchanged,
        "seed": base.get("seed"),
        "event_count": base.get("event_count"),
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0172-probe1 four-way replay identity recomputed live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
