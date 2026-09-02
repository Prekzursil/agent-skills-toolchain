#!/usr/bin/env python3
"""Probe 2: independent order and blocking comparison.

Does not import adapter mapping tables. Reads CLAUDE.md Workflow Enforcement
and orchestrated-execution SKILL.md directly, then checks the IR artifact
(or a freshly built IR) against those offsets and the hand-read sequence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "corpus"
READER = HERE / "fixtures" / "independent-reader-sequence.json"
WORKED = HERE / "fixtures" / "worked-example.json"
OUT = REPO / "command-center" / "wfa" / "WFA-0046-adapter-metaswarm-pipeline.json"

sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402  — build_ir only; order is checked from sources


def first_pos(hay: str, needle: str) -> int:
    i = hay.find(needle)
    if i < 0:
        raise ValueError(f"missing {needle!r}")
    return i


def main() -> int:
    claude = (CORPUS / "CLAUDE.md").read_text(encoding="utf-8")
    orch = (CORPUS / "orchestrated-execution.SKILL.md").read_text(encoding="utf-8")
    usage = (CORPUS / "USAGE.md").read_text(encoding="utf-8")
    start = (CORPUS / "start.SKILL.md").read_text(encoding="utf-8")
    reader = json.loads(READER.read_text(encoding="utf-8"))
    worked = json.loads(WORKED.read_text(encoding="utf-8"))

    enf_start = first_pos(claude, "## Workflow Enforcement (MANDATORY)")
    enf_end = claude.find("## External Tools", enf_start)
    enf = claude[enf_start:enf_end]
    pos_design = first_pos(enf, "Design Review Gate")
    pos_plan = first_pos(enf, "Plan Review Gate")
    pos_reflect = first_pos(enf, "`/self-reflect`")
    gov_order_ok = pos_design < pos_plan < pos_reflect

    loop = [
        ("IMPLEMENT", first_pos(orch, "### Phase 1: IMPLEMENT")),
        ("VALIDATE", first_pos(orch, "### Phase 2: VALIDATE")),
        ("ADVERSARIAL REVIEW", first_pos(orch, "### Phase 3: ADVERSARIAL REVIEW")),
        ("COMMIT", first_pos(orch, "### Phase 4: COMMIT")),
    ]
    loop_order_ok = loop[0][1] < loop[1][1] < loop[2][1] < loop[3][1]
    knowledge_before_pr = "BEFORE creating the PR" in orch
    blocking_prose = "Quality gates are BLOCKING STATE TRANSITIONS" in orch
    fail_not_skip = "FAIL means retry or escalate, never skip" in orch

    ir = A.build_ir()
    gov_ids = [g["id"] for g in ir["governance_mandatory_gates"]]
    reader_ids = reader["mandatory_gate_order"]
    gov_match = gov_ids == reader_ids

    seq = [n["id"] for n in ir["rendered_sequence"]]
    reader_seq = [n["id"] for n in reader["sequence"]]
    seq_match = seq == reader_seq

    blocking_mismatch = []
    ir_block = {n["id"]: n["blocking"] for n in ir["rendered_sequence"]}
    for n in reader["sequence"]:
        if n["id"] in ir_block and bool(n["blocking"]) != bool(ir_block[n["id"]]):
            blocking_mismatch.append(n["id"])
        for sub in n.get("substages") or []:
            if sub["id"] in ir_block and bool(sub["blocking"]) != bool(
                ir_block[sub["id"]]
            ):
                blocking_mismatch.append(sub["id"])

    worked_ok = True
    for step in worked["trace"]:
        nid = step["node_id"]
        if nid not in ir_block:
            worked_ok = False
            continue
        if bool(step["blocking"]) != bool(ir_block[nid]):
            worked_ok = False
        if step["fail_advances"] is True:
            worked_ok = False

    usage_has_nine = all(f"| {i}. " in usage for i in range(1, 10))
    overview = start[first_pos(start, "## Workflow Overview") :]
    overview_has_plan_then_design = first_pos(
        overview, "Plan Review Gate"
    ) < first_pos(overview, "DESIGN REVIEW GATE")

    report = {
        "probe": "probe2-independent-order",
        "governance_offsets": {
            "design_review": pos_design,
            "plan_review": pos_plan,
            "self_reflect": pos_reflect,
            "order_ok": gov_order_ok,
        },
        "loop_offsets_ok": loop_order_ok,
        "knowledge_before_pr": knowledge_before_pr,
        "blocking_prose": blocking_prose,
        "fail_not_skip": fail_not_skip,
        "governance_ids_match_reader": gov_match,
        "rendered_sequence_match_reader": seq_match,
        "blocking_mismatch": blocking_mismatch,
        "worked_example_ok": worked_ok,
        "usage_has_nine": usage_has_nine,
        "start_overview_plan_before_design": overview_has_plan_then_design,
        "ledger_records_order_conflict": any(
            "Plan Review before Design Review" in (row.get("construct") or "")
            for row in ir["lossy_field_ledger"]
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if OUT.is_file():
        art = json.loads(OUT.read_text(encoding="utf-8"))
        art_gov = [g["id"] for g in art["ir"]["governance_mandatory_gates"]]
        if art_gov != gov_ids:
            print("FAILED:WFA-0046-probe2 artifact governance order drifted")
            return 1

    ok = (
        gov_order_ok
        and loop_order_ok
        and knowledge_before_pr
        and blocking_prose
        and fail_not_skip
        and gov_match
        and seq_match
        and not blocking_mismatch
        and worked_ok
        and usage_has_nine
        and overview_has_plan_then_design
        and report["ledger_records_order_conflict"]
    )
    if not ok:
        print("FAILED:WFA-0046-probe2 independent order/blocking comparison")
        return 1
    print(
        "governance_design_then_plan_then_reflect=True "
        "loop_impl_val_rev_commit=True knowledge_before_pr=True "
        "blocking_semantics_match=True"
    )
    print("SUCCESS:WFA-0046-probe2 independent order and blocking")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
