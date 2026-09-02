#!/usr/bin/env python3
"""Probe 1: log-replay four-way identity and dissent preservation.

Source measurement (distinct fingerprint from probe 2). Re-runs the recorded
council against the event log and fails if decision matches while the minority
report is lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay_engine as E  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0172.json"


def main() -> int:
    exp = E.run_experiment(REPO)
    out = {
        "probe": "probe1-replay-identity",
        "unit_id": "CNF-0172",
        "log_replay_all_match": exp["log_replay_identity"]["all_match"],
        "four_diff": exp["log_replay_identity"],
        "four_hashes": exp["recorded"]["four_hashes"],
        "dissent_recorded": exp["dissent_preservation"]["recorded"],
        "dissent_replayed": exp["dissent_preservation"]["replayed"],
        "lossy_decision_match": exp["lossy_dissent_drop"]["decision_match"],
        "lossy_dissent_match": exp["lossy_dissent_drop"]["dissent_match"],
        "lossy_classified_failure": exp["lossy_dissent_drop"]["classified_failure"],
        "fake_clock_seed_rerun_all_match": exp["fake_clock_seed_rerun_identity"]["all_match"],
        "not_replayable": [
            c["component"] for c in exp["honest_scoping"]["not_deterministically_replayable"]
        ],
        "substrate": exp["inventory"]["substrate"],
        "production_runtime_present": exp["inventory"]["production_runtime_present"],
        "pass": bool(
            exp["log_replay_identity"]["all_match"]
            and exp["fake_clock_seed_rerun_identity"]["all_match"]
            and exp["dissent_preservation"]["recorded"]
            and exp["dissent_preservation"]["replayed"]
            and exp["lossy_dissent_drop"]["classified_failure"]
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        print("FAILED:CNF-0172-probe1 identity or dissent")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0172-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0172-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0172" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0172-probe1 sentinel absent")
        return 1
    rec_hashes = ((doc.get("baseline_repro") or {}).get("four_hashes")) or {}
    live_hashes = exp["recorded"]["four_hashes"]
    if rec_hashes != live_hashes:
        print("FAILED:CNF-0172-probe1 receipt four_hashes drift")
        print(json.dumps({"receipt": rec_hashes, "live": live_hashes}, sort_keys=True))
        return 1
    diffs = (doc.get("regression_diff") or {}).get("log_replay") or {}
    if not diffs.get("all_match"):
        print("FAILED:CNF-0172-probe1 receipt log_replay not all_match")
        return 1
    lossy = (doc.get("tests") or {}).get("lossy_dissent_drop") or {}
    if not lossy.get("classified_failure"):
        print("FAILED:CNF-0172-probe1 receipt missing lossy classified_failure")
        return 1
    if not (doc.get("dissent_preservation") or {}).get("replayed"):
        print("FAILED:CNF-0172-probe1 receipt dissent not replayed")
        return 1
    src = doc.get("source_probe") or {}
    ver = doc.get("verifier_probe") or {}
    if not src or not ver:
        print("FAILED:CNF-0172-probe1 source_probe/verifier_probe missing")
        return 1
    if src.get("fingerprint") == ver.get("fingerprint"):
        print("FAILED:CNF-0172-probe1 same-probe-rerun fingerprints")
        return 1
    if not src.get("fingerprint") or not ver.get("fingerprint"):
        print("FAILED:CNF-0172-probe1 empty probe fingerprint")
        return 1
    print(
        "log_replay=True dissent_replayed=True lossy_fires=True "
        f"substrate={out['substrate']}"
    )
    print("SUCCESS:CNF-0172-probe1 log-replay identity and dissent preservation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
