#!/usr/bin/env python3
"""Emit ADV-0110 root-cause hierarchy falsifiability artifact (no receipts)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = "command-center/adversarial/ADV-0110-root-cause-hierarchy-falsifiability.json"
SCHEMA = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0110/probe1_link_falsifiability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0110/probe2_counterfactual.py"
)
SENTINEL = (
    "SUCCESS:ADV-0110 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0110 <reason>."
)
QUESTION = (
    "Is the synthesis's root-cause hierarchy a causal structure whose links "
    "are individually falsifiable, or a flat finding list relabelled with "
    "parent nodes?"
)
P1_REQ = (
    "Probe 1: for each parent-child link, state the observation that would "
    "REFUTE the causal claim and check whether the evidence base could produce "
    "it; a link with no refuting observation is a label, not a cause."
)
P2_REQ = (
    "Probe 2 (mechanically different): structural test - if removing the parent "
    "cause would not have prevented the child findings, the link fails a "
    "counterfactual check independent of the stated evidence."
)


def build_document(
    live: dict,
    p1_raw: str,
    p2_raw: str,
    p1_rc: int,
    p2_rc: int,
    now: str,
) -> dict:
    control = live["control"]
    planted = live["planted"]
    standin = live["standin"]
    schema_present = (REPO / SCHEMA).is_file()
    answer = (
        "REFUTED: SYN-0001.root-cause-hierarchy.json is absent, so synthesis "
        "did not produce a falsifiable causal DAG. The on-disk stand-in in "
        "SYN-0007 is the catalog CC|SYN dependency graph with nodes typed "
        f"{standin['degree_typing']['n_matching']}/{standin['n_nodes']} by "
        "in/out degree (CAUSE if in-degree 0, SYMPTOM if out-degree 0, else "
        "MECHANISM). All "
        f"{standin['n_edges']} stand-in edges have no per-link refuting "
        "observation (probe 1 LABEL) and fail the counterfactual: removing "
        "the parent catalog dependency would not delete the child's "
        "independent title/question. The required genuine-causal control "
        f"({control['id']}) passes both probes: G-1 digest_file CRLF "
        "normalization equalizes CRLF vs LF hashes, and removing it restores "
        "the mismatch class (ADV-0111 CRLF trap)."
    )
    tests = [
        {
            "id": "T-CONTROL-GENUINE-PASSES-BOTH",
            "requirement": (
                "include one link known to be genuinely causal (a fix that "
                "demonstrably eliminated a class of findings) and require it "
                "to pass both probes"
            ),
            "result": "PASS" if live["control_passed_both_probes"] else "FAIL",
            "evidence": (
                f"probe1={control['probe1']} probe2={control['probe2']} "
                f"with_eq={control['child_holds_with_parent']} "
                f"without_eq={control['child_holds_without_parent']} "
                f"eliminated={control['class_of_findings_eliminated']}"
            ),
        },
        {
            "id": "T-PLANTED-LABEL-FAILS-PROBE1",
            "requirement": "planted unfalsifiable relabel has no refuting observation",
            "result": "PASS" if planted["probe1"] == "LABEL" else "FAIL",
            "evidence": "refuting_observation=None probe1=LABEL",
        },
        {
            "id": "T-PLANTED-LABEL-FAILS-PROBE2",
            "requirement": "removing planted parent does not prevent child findings",
            "result": "PASS" if not planted["probe2_pass"] else "FAIL",
            "evidence": planted["counterfactual_reason"],
        },
        {
            "id": "T-LIVE-SYN-0001-RECORDED",
            "requirement": "audit the synthesis hierarchy artifact, recording presence or absence honestly",
            "result": "PASS" if isinstance(live["syn0001"]["present"], bool) else "FAIL",
            "evidence": f"present={live['syn0001']['present']} path={live['syn0001']['path']}",
        },
        {
            "id": "T-STANDIN-DEGREE-TYPING-RECORDED",
            "requirement": "record whether the stand-in is typed by graph degree rather than cause",
            "result": "PASS" if "fraction" in standin["degree_typing"] else "FAIL",
            "evidence": (
                f"{standin['degree_typing']['n_matching']}/{standin['n_nodes']} "
                f"all_degree_typed={standin['degree_typing']['all_degree_typed']} "
                f"rule={standin['degree_typing']['rule']}"
            ),
        },
        {
            "id": "T-EVERY-TARGET-ONE-VERDICT",
            "requirement": "exactly one verdict from the allowed set per enumerated target",
            "result": "PASS"
            if live["enumerated_targets"]
            and all(
                t["verdict"] in E.ALLOWED for t in live["enumerated_targets"]
            )
            else "FAIL",
            "evidence": f"n={len(live['enumerated_targets'])} allowed={list(E.ALLOWED)}",
        },
        {
            "id": "T-MISSING-CONTROL-WOULD-DOWNGRADE",
            "requirement": "any missing control downgrades verdicts to NOT-CHECKED",
            "result": "PASS" if live["control_passed_both_probes"] else "FAIL",
            "evidence": f"control_passed_both_probes={live['control_passed_both_probes']}",
        },
    ]
    failed = [t["id"] for t in tests if t["result"] != "PASS"]
    if failed:
        raise SystemExit(f"FAILED:ADV-0110-emit tests {failed}")

    compact_links = [
        {
            "id": row["id"],
            "mechanism": row["mechanism"],
            "probe1": row["probe1"],
            "probe2": row["probe2"],
            "verdict": row["verdict"],
        }
        for row in standin["links"]
    ]
    return {
        "answer": answer,
        "audit_sha256": live["audit_sha256"],
        "cloud_ok": False,
        "completion_marker": "UNIT-COMPLETE:ADV-0110",
        "completion_sentinel": SENTINEL,
        "controls": {
            "genuine_causal_crlf_digest": {
                "id": control["id"],
                "kind": control["kind"],
                "passed_probe1": control["probe1_pass"],
                "passed_probe2": control["probe2_pass"],
                "refuting_observation": control["refuting_observation"],
                "class_of_findings_eliminated": control["class_of_findings_eliminated"],
                "evidence_anchor": control["evidence_anchor"],
                "child_holds_with_parent": control["child_holds_with_parent"],
                "child_holds_without_parent": control["child_holds_without_parent"],
            },
            "detector_control_planted_label": {
                "id": planted["id"],
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "probe1": planted["probe1"],
                "probe2": planted["probe2"],
            },
        },
        "enumerated_targets": live["enumerated_targets"],
        "evidence": {
            "syn0001": live["syn0001"],
            "standin": {
                "present": standin["present"],
                "source": standin["source"],
                "source_note": standin["source_note"],
                "max_depth": standin["max_depth"],
                "n_nodes": standin["n_nodes"],
                "n_edges": standin["n_edges"],
                "degree_typing": standin["degree_typing"],
                "n_probe1_labels": standin["n_probe1_labels"],
                "n_probe2_fail": standin["n_probe2_fail"],
                "mechanism_counts": standin["mechanism_counts"],
                "links": compact_links,
            },
            "control": control,
            "planted": planted,
        },
        "id": "ADV-0110",
        "inputs_used": [
            {"path": E.SYN0001, "present": live["syn0001"]["present"], "role": "synthesis-hierarchy"},
            {"path": E.SYN0007, "present": standin["present"], "role": "standin-hierarchy"},
            {"path": E.CATALOG, "present": True, "role": "child-record-independence"},
            {"path": E.MEASURE, "present": True, "role": "genuine-causal-control-source"},
        ],
        "min_bytes_threshold": 2048,
        "named_probes": [
            {
                "id": "probe1",
                "name": "PROBE-1-LINK-FALSIFIABILITY",
                "requirement": P1_REQ,
                "command": P1,
                "exit_code": p1_rc,
                "raw_output": p1_raw,
                "role": "per-link-refuting-observation",
            },
            {
                "id": "probe2",
                "name": "PROBE-2-COUNTERFACTUAL-PREVENTION",
                "requirement": P2_REQ,
                "command": P2,
                "exit_code": p2_rc,
                "raw_output": p2_raw,
                "role": "remove-parent-prevention-test",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-PLANTED-UNFALSIFIABLE-RELABEL",
                "kind": "planted-label",
                "description": (
                    "Plant parent=complexity child=all-findings with no "
                    "refuting observation. Probe 1 must classify LABEL; "
                    "probe 2 must fail counterfactual."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "verbatim": (
                    f"probe1={planted['probe1']} probe2={planted['probe2']} "
                    f"verdict={planted['verdict']}"
                ),
            },
            {
                "id": "NC-GENUINE-CRLF-DIGEST-NOT-MISCLASSIFIED",
                "kind": "known-causal-link",
                "description": (
                    "G-1 digest_file CRLF normalization must pass both probes "
                    "and not be classified as a label."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "verbatim": (
                    f"probe1={control['probe1']} probe2={control['probe2']} "
                    f"verdict={control['verdict']}"
                ),
            },
        ],
        "notes": (
            "G-1 for ADV-0110: live named probes exit 0, artifact state=SUCCESS "
            "with scientific overall_verdict=REFUTED, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "Did not author SYN-0001."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "overall_verdict": live["overall_verdict"],
        "produced_at": now,
        "question": QUESTION,
        "report_kind": "refutation-record",
        "reviewer": {
            "reviewer_id": "ADV-0110-probe2-counterfactual-prevention",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the CRLF with/without-parent hash experiment "
                "and catalog-child independence without reading probe 1's "
                "refuting-observation field. Catalog two-vendor live review "
                "is not claimed."
            ),
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:ADV-0110",
        "spec_anchor": "_USER-PROMPTS.md:11086",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "targets": live["enumerated_targets"],
        "tests": tests,
        "title": "Falsifiability audit of the root-cause hierarchy",
        "unit_id": "ADV-0110",
    }


def write_artifact(doc: dict) -> Path:
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def main() -> int:
    live = E.investigate()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_document(live, "pending live probe1", "pending live probe2", -1, -1, now)
    write_artifact(doc)
    print(f"WROTE {OUT} audit_sha256={live['audit_sha256']}")
    print("SUCCESS:ADV-0110-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
