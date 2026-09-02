#!/usr/bin/env python3
"""Probe 2: seed perturbation, drop-participant diff, second-run classes.

Verifier measurement (distinct fingerprint from probe 1). Does not re-read
probe 1's four-hash identity; it reads transcript-change, drop-participant
diff fire, and nondeterminism-class equality across two recorded runs.
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
    sp = exp["seed_perturbation"]
    drop = exp["drop_participant"]
    second = exp["second_recorded_run"]
    live = exp["live_clock_arm"]
    out = {
        "probe": "probe2-controls-second-run",
        "unit_id": "CNF-0172",
        "seed_transcript_changed": sp["transcript_changed"],
        "drop_participant_diff_fired": drop["diff_fired"],
        "drop_dissent_diff_fired": drop["dissent_diff_fired"],
        "drop_dissent_empty": drop["dissent_empty"],
        "drop_decision_still_present": drop["decision_still_present"],
        "second_run_log_replay_all_match": second["log_replay_identity"]["all_match"],
        "second_run_dissent_intact": second["dissent_intact"],
        "nondeterminism_classes_equal": second["classes_equal_run1"],
        "nondeterminism_classes": second["nondeterminism_classes"],
        "live_clock_semantic_match": live["semantic_all_match"],
        "live_clock_wall_clock_diverged": live["wall_clock_diverged"],
        "pass": bool(
            sp["transcript_changed"]
            and drop["dissent_diff_fired"]
            and drop["dissent_empty"]
            and drop["decision_still_present"]
            and second["log_replay_identity"]["all_match"]
            and second["dissent_intact"]
            and second["classes_equal_run1"]
            and live["semantic_all_match"]
            and live["wall_clock_diverged"]
        ),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["pass"]:
        print("FAILED:CNF-0172-probe2 controls")
        return 1
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0172-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    tests = doc.get("tests") or {}
    rec_seed = tests.get("seed_perturbation") or {}
    if not rec_seed.get("transcript_changed"):
        print("FAILED:CNF-0172-probe2 receipt seed control missing")
        return 1
    if rec_seed.get("transcript_a") != sp["transcript_a"]:
        print("FAILED:CNF-0172-probe2 transcript_a drift")
        return 1
    rec_drop = tests.get("drop_participant") or {}
    if not rec_drop.get("dissent_diff_fired"):
        print("FAILED:CNF-0172-probe2 receipt drop control missing")
        return 1
    rec_second = tests.get("second_recorded_run") or {}
    if not rec_second.get("classes_equal_run1"):
        print("FAILED:CNF-0172-probe2 receipt second-run classes missing")
        return 1
    if not rec_second.get("dissent_intact"):
        print("FAILED:CNF-0172-probe2 receipt second-run dissent missing")
        return 1
    scoped = doc.get("honest_scoping") or {}
    named = {c.get("component") for c in (scoped.get("not_deterministically_replayable") or [])}
    if "wall_clock" not in named or "live_model_token_stream" not in named:
        print("FAILED:CNF-0172-probe2 honest scoping omitted a non-replayable component")
        return 1
    print(
        f"seed_changed={sp['transcript_changed']} drop_fires={drop['dissent_diff_fired']} "
        f"classes_equal={second['classes_equal_run1']} live_clock_diverged={live['wall_clock_diverged']}"
    )
    print("SUCCESS:CNF-0172-probe2 seed/drop/second-run controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
