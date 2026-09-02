#!/usr/bin/env python3
"""Both-states: unaltered MATCH; one-stage mutant names that stage index.

Naive candidate_id equality is the false-green control on the mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import differential as D  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0154-executed-corpus-replay-differential-for-the-72-h-fam.json"
MUTATE_INDEX = 1
MUTANT = "PLANTED-STAGE-MUTANT"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0154-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")

    C.materialize()
    runs = C.load_runs()
    bps = C.load_blueprints()
    cid = C.cid(0)
    rec = runs.get(cid)
    bp = bps.get(cid)
    if rec is None or bp is None:
        return fail("control-pair-missing h-exec-00")

    ctrl = D.both_states_control(rec, bp, mutate_index=MUTATE_INDEX, mutant_name=MUTANT)
    print(ctrl["what"])
    print(
        f"unaltered verdict={ctrl['unaltered']['verdict']} "
        f"div={ctrl['unaltered']['divergence_count']} "
        f"tid={ctrl['unaltered']['transcript_record_id']}"
    )
    print(
        f"altered verdict={ctrl['altered']['verdict']} "
        f"named_stage_index={ctrl['altered']['named_stage_index']} "
        f"want={MUTATE_INDEX} "
        f"recorded={ctrl['altered']['recorded_stage']!r} "
        f"reconstructed={ctrl['altered']['reconstructed_stage']!r}"
    )
    print(f"naive_id_only_on_altered={ctrl['naive_id_only_on_altered']}")

    if ctrl["unaltered"]["verdict"] != D.MATCH:
        return fail("unaltered-not-MATCH")
    if ctrl["unaltered"]["divergence_count"] != 0:
        return fail("unaltered-nonzero-divergence")
    if ctrl["altered"]["verdict"] != D.CONTRADICTED:
        return fail("altered-not-CONTRADICTED")
    if ctrl["altered"]["named_stage_index"] != MUTATE_INDEX:
        return fail(
            f"altered-did-not-name-stage-{MUTATE_INDEX} "
            f"got={ctrl['altered']['named_stage_index']}"
        )
    if ctrl["naive_id_only_on_altered"] != D.MATCH:
        return fail("naive-control-dead; id-only should MATCH the mutant")
    if not ctrl["pass"]:
        return fail("both-states-pass-false")

    planted = C.cid(60)
    rec60 = runs[planted]
    bp60 = bps[planted]
    cmp60 = D.compare_pair(rec60, bp60)
    first = cmp60.get("first_divergence") or {}
    print(
        f"planted {planted} verdict={cmp60['verdict']} "
        f"axis={first.get('axis')} stage_index={first.get('stage_index')} "
        f"tid={cmp60.get('transcript_record_id')}"
    )
    if cmp60["verdict"] != D.CONTRADICTED:
        return fail("planted-60-not-CONTRADICTED")
    if first.get("axis") != "stages" or first.get("stage_index") != 1:
        return fail("planted-60-did-not-name-stage-1")

    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_ctrl = doc.get("both_states") or {}
    if art_ctrl.get("pass") is not True:
        return fail("artifact-both_states.pass")
    if art_ctrl.get("altered", {}).get("named_stage_index") != MUTATE_INDEX:
        return fail("artifact-altered-stage-index-drift")
    if art_ctrl.get("unaltered", {}).get("verdict") != D.MATCH:
        return fail("artifact-unaltered-drift")
    if art_ctrl.get("naive_id_only_on_altered") != D.MATCH:
        return fail("artifact-naive-control-drift")

    art_rows = {r["candidate_id"]: r for r in doc.get("rows") or []}
    row60 = art_rows.get(planted) or {}
    if row60.get("verdict") != D.CONTRADICTED:
        return fail("artifact-row-60-verdict")
    fd = row60.get("first_divergence") or {}
    if fd.get("stage_index") != 1 or fd.get("axis") != "stages":
        return fail("artifact-row-60-first-divergence")
    if row60.get("transcript_record_id") != rec60["transcript_record_id"]:
        return fail("artifact-row-60-transcript-id")

    neg = doc.get("negative_control") or {}
    if not neg.get("naive_id_only_false_green"):
        return fail("artifact-negative-control-unrecorded")

    print("SUCCESS:WFA-0154-probe2 both-states FIRE on planted-stage SILENT on unaltered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
