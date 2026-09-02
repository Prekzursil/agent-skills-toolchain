#!/usr/bin/env python3
"""Probe 1: information-loss measurement on the same fixture.

Compares pipeline judge input against full-transcript judge input.
Signal 1 = token-id set algebra. Signal 2 = canonical sha256 + byte-length.
Also checks the design note cites the live numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0032-proposer-critic-judge-pipeline-topology.md"
EXPECTED_DEFECT = {"CL-DROP", "E1", "Q1"}
EXPECTED_POINT = {"proposer-A", "critic-B", "CL-RHET", "ALT-1"}


def main() -> int:
    run = P.load_run()
    live = P.measure(run)
    s1 = live["signal1_token_sets"]
    s2 = live["signal2_canonical_bytes"]
    rulings = live["rulings"]
    defect = set(s1["defect_lost_ids"])
    point = set(s1["point_lost_ids"])

    print("fixture=" + str(live["fixture_id"]))
    print(
        "signal1_token_sets full="
        + ",".join(s1["full_ids"])
        + " pipeline="
        + ",".join(s1["pipeline_ids"])
        + " lost="
        + ",".join(s1["lost_ids"])
        + " defect_lost="
        + ",".join(s1["defect_lost_ids"])
        + " point_lost="
        + ",".join(s1["point_lost_ids"])
    )
    print(
        "signal2_canonical_bytes pipeline_sha256="
        + s2["pipeline_sha256"]
        + " pipeline_bytes="
        + str(s2["pipeline_bytes"])
        + " full_sha256="
        + s2["full_sha256"]
        + " full_bytes="
        + str(s2["full_bytes"])
        + " sha256_match="
        + str(s2["sha256_match"])
        + " byte_delta="
        + str(s2["byte_delta"])
    )
    print(
        "rulings pipeline="
        + rulings["pipeline_verdict"]
        + " full="
        + rulings["full_transcript_verdict"]
        + " diverge="
        + str(rulings["verdicts_diverge"])
        + " unaddressed="
        + ",".join(rulings["unaddressed_required_ids"])
    )

    if defect != EXPECTED_DEFECT:
        print("FAILED:CNL-0032-probe1 defect_lost mismatch", sorted(defect))
        return 1
    if not EXPECTED_POINT.issubset(point):
        print("FAILED:CNL-0032-probe1 point_lost missing expected", sorted(point))
        return 1
    if s2["sha256_match"] or s2["byte_delta"] <= 0:
        print("FAILED:CNL-0032-probe1 signal2 did not discriminate")
        return 1
    if not rulings["verdicts_diverge"]:
        print("FAILED:CNL-0032-probe1 mechanical rulings did not diverge")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0032-probe1 design note missing")
        return 1
    try:
        note = json.loads(ART.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("FAILED:CNL-0032-probe1 design note unparseable", type(exc).__name__)
        return 1
    if "SUCCESS:CNL-0032" not in json.dumps(note):
        print("FAILED:CNL-0032-probe1 sentinel absent")
        return 1
    cited = note.get("information_loss") or {}
    cited_def = set(cited.get("defect_lost_ids") or [])
    if cited_def != defect:
        print("FAILED:CNL-0032-probe1 note defect_lost_ids != live", sorted(cited_def))
        return 1
    cited_s2 = cited.get("signal2_canonical_bytes") or {}
    if cited_s2.get("pipeline_sha256") != s2["pipeline_sha256"]:
        print("FAILED:CNL-0032-probe1 note pipeline_sha256 != live")
        return 1
    if cited_s2.get("full_sha256") != s2["full_sha256"]:
        print("FAILED:CNL-0032-probe1 note full_sha256 != live")
        return 1
    if cited_s2.get("pipeline_bytes") != s2["pipeline_bytes"]:
        print("FAILED:CNL-0032-probe1 note pipeline_bytes != live")
        return 1
    print("SUCCESS:CNL-0032-probe1 information-loss measurement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
