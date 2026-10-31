#!/usr/bin/env python3
"""Probe 1: re-run held-out evaluation against the live frozen index.

Mechanically the source probe: recomputes recall/precision/tokens and the four
required controls from fixtures on disk, then checks the confirmation record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / H.ARTIFACT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        print("FAILED:CNF-0177-probe1 artifact missing or tiny")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0177":
        print("FAILED:CNF-0177-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:CNF-0177" not in text:
        print("FAILED:CNF-0177-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0177-probe1 self-declared {st}")
        return 1
    if not doc.get("source_probe") or not doc.get("verifier_probe"):
        print("FAILED:CNF-0177-probe1 empty source/verifier probe")
        return 1
    if doc["source_probe"] == doc["verifier_probe"]:
        print("FAILED:CNF-0177-probe1 same-probe-rerun")
        return 1

    for name in ("frozen-index.json", "heldout-tasks.json", "tuning-corpus.json"):
        if not (H.FIX / name).is_file():
            print(f"FAILED:CNF-0177-probe1 missing fixture {name}")
            return 1

    bundle = H.load_frozen()
    proof = H.heldout_proof(bundle)
    ev = H.evaluate_bundle(bundle)
    if not proof["pass"]:
        print("FAILED:CNF-0177-probe1 held-out proof", json.dumps(proof, sort_keys=True))
        return 1
    if not ev["detector_live"]:
        print("FAILED:CNF-0177-probe1 detector not live")
        print(json.dumps(ev["controls"], indent=2, sort_keys=True)[:4000])
        return 1

    live_rec = ev["production_metrics"]["recall"]
    art_rec = (doc.get("metrics") or {}).get("production") or {}
    if art_rec.get("recall") != live_rec:
        print(f"FAILED:CNF-0177-probe1 production recall artifact={art_rec.get('recall')} live={live_rec}")
        return 1
    live_irec = ev["instrument_metrics"]["recall"]
    art_irec = (doc.get("metrics") or {}).get("instrument") or {}
    if art_irec.get("recall") != live_irec:
        print(f"FAILED:CNF-0177-probe1 instrument recall artifact={art_irec.get('recall')} live={live_irec}")
        return 1

    tokens_art = doc.get("token_volume_per_task") or []
    if len(tokens_art) != len(ev["token_volume_per_task"]):
        print("FAILED:CNF-0177-probe1 token volume length mismatch")
        return 1
    for a, b in zip(tokens_art, ev["token_volume_per_task"]):
        if a.get("id") != b.get("id") or a.get("production") != b.get("production"):
            print("FAILED:CNF-0177-probe1 token volume mismatch", a, b)
            return 1

    if ev["controls"]["production"]["known_present"]["pass"]:
        print("FAILED:CNF-0177-probe1 production known-present unexpectedly passed")
        return 1
    if not ev["controls"]["instrument"]["known_present"]["pass"]:
        print("FAILED:CNF-0177-probe1 instrument known-present failed; held-out set not discriminating")
        return 1
    if not ev["controls"]["instrument"]["known_absent"]["pass"]:
        print("FAILED:CNF-0177-probe1 instrument known-absent failed")
        return 1
    if not ev["controls"]["instrument"]["flooding"]["pass"]:
        print("FAILED:CNF-0177-probe1 instrument flooding failed")
        return 1
    if ev["controls"]["flood_mutant"]["flooding"]["pass"]:
        print("FAILED:CNF-0177-probe1 flood mutant stayed under budget (detector silent)")
        return 1
    if not ev["controls"]["instrument"]["both_states"]["pass"]:
        print("FAILED:CNF-0177-probe1 instrument both-states failed")
        return 1
    if not ev["controls"]["production"]["spec_11330"]["reproduced"]:
        print("FAILED:CNF-0177-probe1 spec:11330 not reproduced on production")
        return 1
    if not ev["controls"]["instrument"]["spec_11330"]["reproduced"]:
        print("FAILED:CNF-0177-probe1 spec:11330 synonym miss not reproduced on instrument")
        return 1
    if doc.get("verdict") not in {"REFUTED", "CONFIRMED", "PARTIAL"}:
        print("FAILED:CNF-0177-probe1 verdict", doc.get("verdict"))
        return 1
    if not ev["production_discovery"]["any_present"] and doc.get("verdict") != "REFUTED":
        print("FAILED:CNF-0177-probe1 absent production must REFUTE not", doc.get("verdict"))
        return 1

    n_tasks = len(bundle["heldout"]["tasks"])
    summary = {
        "probe": "probe1-heldout",
        "unit_id": "CNF-0177",
        "n_heldout": n_tasks,
        "heldout_after_freeze": proof["authored_after_freeze"],
        "never_in_tuning": proof["never_in_tuning_corpus"],
        "production_recall": live_rec,
        "instrument_recall": live_irec,
        "production_known_present": ev["controls"]["production"]["known_present"]["pass"],
        "instrument_known_present": ev["controls"]["instrument"]["known_present"]["pass"],
        "instrument_both_states": ev["controls"]["instrument"]["both_states"]["pass"],
        "flood_mutant_exceeds_budget": not ev["controls"]["flood_mutant"]["flooding"]["pass"],
        "spec_11330_reproduced": True,
        "detector_live": True,
        "verdict": doc.get("verdict"),
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:CNF-0177-probe1 held-out evaluation and required controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
