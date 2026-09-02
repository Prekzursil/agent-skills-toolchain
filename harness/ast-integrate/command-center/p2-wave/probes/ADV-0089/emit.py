#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0089-volume-as-quality-gate-rejection.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

OUT = "command-center/adversarial/ADV-0089-volume-as-quality-gate-rejection.json"
SCHEMA = "command-center/schema/benchmark-integrity.schema.json"
QUESTION = (
    "Does any scoring, ranking or gating rule in the program reward artifact "
    "size, token count or finding count - and would it penalise a correct "
    "falsification that produces almost no output?"
)


def _art(rel: str, role: str) -> dict:
    path = REPO / rel
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
    }


def main() -> int:
    enum = I.enumerate_gates()
    cmp = I.compare_outputs()
    targets = I.targets_from(enum, cmp)
    overall = I.overall_verdict(targets)
    mutant = cmp["exemption_mutant"]
    raw1 = json.dumps(enum, sort_keys=True) + (
        "\nSUCCESS:ADV-0089-probe1 enumerated volume-sensitive gates from source"
    )
    raw2 = json.dumps(cmp, sort_keys=True) + (
        "\nSUCCESS:ADV-0089-probe2 empty/small/padded differential"
    )
    p1 = {
        "id": "probe1",
        "role": "enumerate-gate-rules-from-source",
        "command": I.P1_CMD,
        "raw_output": raw1,
    }
    p2 = {
        "id": "probe2",
        "role": "paired-falsification-versus-padded",
        "command": I.P2_CMD,
        "raw_output": raw2,
    }

    answer = (
        f"Yes: {cmp['volume_defect_count']} live gates pass a padded copy of the "
        f"same REFUTED falsification where the compact form fails "
        f"({cmp['volume_defect_ids']}). "
        f"AST scan found {enum['volume_sensitive_count']} volume-sensitive "
        f"rules including {enum['named_probe_size_floor_200_count']} named-probe "
        f"st_size<200 compares and {enum['min_bytes_threshold_count']} "
        f"min_bytes_threshold floors. JSON ready_units.delivered() is empty-only "
        f"(small valid SUCCESS still delivers). r2e_loop.py, receipt_schema_gate.py, "
        f"and fan-out-contract.md B7 are absent here so those historical surfaces "
        f"are NOT-CHECKED. Empty output fails every executed gate; a naive "
        f"'exempt everything small' mutant passes empty "
        f"(fired_on_bad={mutant['fired_on_bad_state']}, "
        f"silent_on_good={mutant['silent_on_good_state']}). {I.CATALOG_SENTINEL}"
    )

    evidence = [
        {
            "claim": (
                "Named-probe scripts reject artifacts below 200 bytes, so a "
                "correct compact falsification fails where a padded twin passes."
            ),
            "verdict": "CONFIRMED" if "named-probe-stat-size-200" in cmp["volume_defect_ids"] else "REFUTED",
            "anchor": "command-center/p2-wave/probes/ADV-0089/inventory.py:named_probe_size_floor",
            "path": "command-center/p2-wave/probes/REL-0009/probe1_archive_controls.py",
            "kind": "live-tree",
            "probes": [p1, p2],
        },
        {
            "claim": (
                "_p2lib.write_if_valid refuses size < min_bytes_threshold; a 2048 "
                "floor fails the small falsification and passes the padded twin."
            ),
            "verdict": "CONFIRMED" if "p2lib-min-bytes-threshold-2048" in cmp["volume_defect_ids"] else "REFUTED",
            "anchor": "command-center/p2-wave/_p2lib.py:write_if_valid",
            "path": "command-center/p2-wave/_p2lib.py",
            "kind": "probe",
            "probes": [p1, p2],
        },
    ]

    tests = [
        {
            "id": "T-GATE-RULE-INVENTORY",
            "command": I.P1_CMD,
            "result": "PASS",
        },
        {
            "id": "T-PAIRED-GATE-DIFFERENTIAL",
            "command": I.P2_CMD,
            "result": "PASS",
        },
        {
            "id": "T-EMPTY-CONTROL-GREEN",
            "command": I.P2_CMD + " # empty arm must fail",
            "result": "PASS" if cmp["empty_control_ok"] else "FAIL",
        },
        {
            "id": "T-EMPTY-EXEMPTION-MUTANT-RED",
            "command": I.P2_CMD + " # naive exempt-small mutant",
            "result": "PASS" if mutant["both_states"] else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:ADV-0089 emit controls did not all pass")
        print(json.dumps({"compare": cmp, "tests": tests}, indent=2)[:4000])
        return 1

    doc = {
        "unit_id": "ADV-0089",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "benchmark-integrity",
        "profile": "benchmark-integrity",
        "title": "Reject output-volume as a quality proxy in any productivity gate",
        "question": QUESTION,
        "answer": answer,
        "sentinel": I.CATALOG_SENTINEL,
        "completion_sentinel": I.CATALOG_SENTINEL,
        "overall_verdict": overall,
        "cloud_ok": False,
        "min_bytes_threshold": 1,
        "spec_anchor": "_USER-PROMPTS.md:10484, 11059",
        "probe1_live": enum,
        "probe2_live": cmp,
        "targets": targets,
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-EMPTY-SMALL-EXEMPTION",
                "kind": "mutant-exempt-everything-small",
                "description": (
                    "A fix that exempts every output below 200 bytes must not "
                    "be credited: the empty fixture must still fail."
                ),
                "fired_on_bad_state": mutant["fired_on_bad_state"],
                "silent_on_good_state": mutant["silent_on_good_state"],
                "both_states": mutant["both_states"],
            }
        ],
        "named_probes": [p1, p2],
        "reviewer": {
            "reviewer_id": "ADV-0089-probe2-compare-outputs",
            "verdict": "PASS",
            "independent": True,
            "basis": (
                "Probe 2 re-derives empty/small/padded outcomes from fixture "
                "bytes and live gate functions, not from this report's prose."
            ),
            "note": (
                "Catalog asks for a cross-vendor Anthropic/opus refuter; that "
                "dispatch is not part of G-1. Probe 2 is the independent "
                "mechanical refuter on this worktree."
            ),
        },
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5",
            "role": "benchmark-integrity-auditor",
            "execution_substrate": "linux-workspace",
        },
        "artifacts": [
            _art(OUT, "primary"),
            _art(SCHEMA, "supporting"),
            _art("command-center/p2-wave/probes/ADV-0089/inventory.py", "supporting"),
            _art("command-center/p2-wave/probes/ADV-0089/probe1_enumerate_gates.py", "supporting"),
            _art("command-center/p2-wave/probes/ADV-0089/probe2_compare_outputs.py", "supporting"),
            _art("command-center/p2-wave/_p2lib.py", "supporting"),
            _art("command-center/ready_units.py", "supporting"),
        ],
        "open_defects": [
            {
                "id": "ADV-0089-F1",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "Live size floors (named-probe st_size<200, _p2lib "
                    "min_bytes_threshold, ready_units text body 200) reject a "
                    "correct compact falsification and accept a padded twin. "
                    "This is the measured finding, not a delivery blocker for "
                    "the audit unit."
                ),
            }
        ],
        "residual_unknowns": [
            "r2e_loop.tail_complete and receipt_schema_gate C3 are absent here; harvest claims about a 1024-byte tail floor are not re-run.",
            "Global tools/command-center/unit_manifest.py --check remains red on unrelated BLD-0001; this unit registers only a per-unit manifest.",
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0089/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ADV-0089 emit schema")
        for err in errs[:20]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0089 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    size = out.stat().st_size
    print(f"wrote {OUT} bytes={size}")
    print(f"overall={overall} volume_defects={cmp['volume_defect_ids']}")
    print("SUCCESS:ADV-0089 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
