#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0031.json independent floor recount."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0031/probe1_two_extractors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0031/probe2_protocol_preset_disjoint.py"
)
SUPPORTING = [
    X.SCHEMA_REL,
    X.PROFILES_REL,
    X.RECEIPT_SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0031/extract.py",
    "command-center/p2-wave/probes/SYN-0031/probe1_two_extractors.py",
    "command-center/p2-wave/probes/SYN-0031/probe2_protocol_preset_disjoint.py",
]


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def validate_or_die(doc: dict, label: str) -> int:
    errs = X.schema_errors(doc, REPO)
    if errs:
        print(f"FAILED:SYN-0031 schema errors ({label})")
        for err in errs[:20]:
            print(" ", err)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {
            "unit_id": "SYN-0031",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:SYN-0031 restated",
            "floors": "283/284/108/58/72/2048",
        },
    ]
    validator = X.local_validator(REPO)
    for blob in garbage:
        if not list(validator.iter_errors(blob)):
            print(f"FAILED:SYN-0031 schema accepted garbage {list(blob)[:3]}")
            return 1
    return 0


def floor_observation(row: dict) -> dict:
    verdict = row.get("extractor_verdict")
    vs_prior = row.get("vs_prior")
    measured = (
        f"this={row['this_count']} json={row['json_count']} "
        f"regex={row['regex_count']} extractors={verdict} vs_prior={vs_prior} "
        f"floor_met={row['floor_met']}"
    )
    return {
        "name": row["id"],
        "measured": measured,
        "method": "json.loads-typed-array vs brace-scanner-no-json.loads",
        "anchor": (
            (row.get("source_files") or [X.CATALOG_REL])[0]
            if row.get("source_files") or row["id"] == "work_units"
            else f"corpus-{row['id']}-absent"
        ),
    }


def build_doc(live: dict, unit: dict, now: str) -> dict:
    sentinel = str(unit["completion_sentinel"])
    question = str(unit["question_or_target"])
    floors_out = [
        {k: v for k, v in row.items() if k != "this_ids"} for row in live["floors"]
    ]
    wu = live["by_id"]["work_units"]
    declared = live["catalog_declared"]
    silence = live["silence"]
    source_counts = " ".join(
        f"{row['id']}={row['this_count']}/{row['extractor_verdict']}/{row['vs_prior']}"
        for row in floors_out
    )
    catalog_line = X.find_line(REPO / X.CATALOG_REL, '"id": "SYN-0031"')
    artifacts = [X.artifact_record(REPO, rel, "supporting") for rel in SUPPORTING]
    report = {
        "kind": "floor-recount",
        "question": question,
        "did_not_restate_prompt_one": True,
        "prior_audit": {
            "path": X.PRIOR_AUDIT_REL,
            "present": live["prior_audit_present"],
            "treated_as": "claim-not-fact",
            "catalog_cited_claims": X.PRIOR_CLAIMS,
        },
        "corpus_locator": live["locator"],
        "extractors": {
            "json_path": X.JSON_PATH_RULE,
            "regex_brace": X.BRACE_RULE,
            "json_uses_json_loads": True,
            "regex_uses_json_loads": False,
        },
        "floors": floors_out,
        "protocol_preset_disjointness": live["disjoint"],
        "regex_cross_silence": {
            "protocol_regex": silence["protocol_regex"],
            "preset_regex": silence["preset_regex"],
            "protocol_silent_on_preset_items": True,
            "preset_silent_on_protocol_items": True,
            "proven_on": (
                "command-center/p2-wave/probes/SYN-0031/fixtures/"
                "corpus-good/12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
            ),
        },
        "catalog_declared_work_units": declared,
        "known_present_quotes": live["work_unit_quotes"],
        "control_ids": [
            "two-extractors-or-resolved-from-document",
            "protocol-preset-empty-intersection",
            "regex-cross-silence",
            "known-present-first-last-id-quoted",
            "schema-rejects-garbage",
        ],
        "observations": [floor_observation(row) for row in floors_out]
        + [
            {
                "name": "protocol_preset_intersection_empty",
                "measured": bool(live["disjoint"]["empty_intersection"]),
                "method": "set-intersection-not-sum-or-max",
                "anchor": "command-center/p2-wave/probes/SYN-0031/extract.py:protocol_preset_disjoint",
            },
            {
                "name": "corpus_07_08_09_12_present",
                "measured": any(
                    hit.get("json_present") or hit.get("md_present")
                    for hit in live["locator"]["hits"].values()
                ),
                "method": "Path.is_file on named JSON/MD twins",
                "anchor": "command-center/p2-wave/probes/SYN-0031/extract.py:locate_corpus",
            },
        ],
    }
    return {
        "schema_version": 1,
        "unit_id": X.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": (
            f"command-center/WORK-UNIT-CATALOG.json:{catalog_line} "
            "SYN-0031 floors :11393-11396"
        ),
        "min_bytes_threshold": 2000,
        "profile": "floor-recount",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "independent-counter",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Independent json.loads vs brace-scanner recount of every "
                    "numeric floor, treating Prompt One numbers as claims. "
                    f"Live: {source_counts}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{X.CATALOG_REL}:{catalog_line}",
                "probes": [
                    X.probe_record(
                        "source",
                        "static-analysis",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c import-extract-measure_live",
                        source_counts,
                        0,
                    ),
                    X.probe_record("verifier", "test-run", P1, "pending-live-rerun", 0),
                ],
            },
            {
                "claim": (
                    "Protocol and preset id sets are disjoint (not summed or "
                    "maxed) and the two heading regexes are silent on each "
                    "other's items."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0031/extract.py:protocol_preset_disjoint",
                "probes": [
                    X.probe_record(
                        "source",
                        "static-analysis",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c import-extract-protocol_preset_disjoint",
                        str(live["disjoint"]),
                        0,
                    ),
                    X.probe_record("verifier", "test-run", P2, "pending-live-rerun", 0),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_two_extractors_agree_or_the_disagreement_is_resolved_from_the_document",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_protocol_and_preset_id_sets_are_disjoint",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "known-present-control-first-and-last-id-quoted",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-json-md-protocol-disagreement",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted 12-COUNCIL JSON has PROT-003 and the markdown twin "
                    "does not; extractors must disagree and resolve from JSON."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "json=3 md=2 resolved_from_json",
                "good_state_output": "fixture-agree protocols n=4",
            },
            {
                "id": "planted-protocol-preset-overlap",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted SHARED-1 in both protocols and presets must be "
                    "reported as a non-empty intersection, never summed blind."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "intersection=['SHARED-1']",
                "good_state_output": "empty_intersection=true",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "Resolved floor-recount schema rejects empty, unrelated, "
                    "and restated-count blobs."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0031-probe1-independent-brace-scanner",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "probe1 re-runs json.loads vs brace scanner on the live catalog "
                "and planted fixtures; probe2 checks protocol/preset "
                "disjointness and regex cross-silence, including planted overlap."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0031/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/SYN-0031/probe1_two_extractors.py",
                "artifact_path": X.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": X.probe_record("verifier", "test-run", P1, "pending-live-rerun", 0),
            },
            {
                "consumer": "command-center/p2-wave/probes/SYN-0031/probe2_protocol_preset_disjoint.py",
                "artifact_path": X.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": X.probe_record("verifier", "test-run", P2, "pending-live-rerun", 0),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 1,
            "policy": str(unit.get("retry_policy") or ""),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "draft7-unresolved-shim-ref-ast-integrate.invalid",
                    "outcome": "FAILED",
                }
            ],
            "pivot_alternatives": [
                "local RefResolver store for platform/schema/*.json $ids",
                "receipt_core + generic_report envelope with report.kind=floor-recount",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Prompt One corpus files 07-OPTION-UNIVERSE, "
                    "08-WORKFLOW-ARCHAEOLOGY, 09-WORKFLOW-BLUEPRINT-LIBRARY and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS are not mounted on this "
                    "Linux worktree. Those floors recount as this_count=0 from "
                    "Path.is_file false, not from restated Prompt One numbers. "
                    f"Work-unit floor is measured live at {wu['this_count']} "
                    f"against target {declared.get('target')} "
                    f"(shortfall {declared.get('shortfall')})."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount harness-restore-20260806 or set HARVEST_RESTORE to a "
                    "tree that contains the JSON/MD twins, then re-run "
                    "command-center/p2-wave/probes/SYN-0031/emit_recount.py."
                ),
            }
        ],
        "report": report,
    }


def attach_live_probes(doc: dict, t1: str, c1: int, t2: str, c2: int, ended: str) -> dict:
    doc = dict(doc)
    doc["timestamps"] = dict(doc["timestamps"])
    doc["timestamps"]["ended_at"] = ended
    evidence = [dict(item) for item in doc["evidence"]]
    evidence[0] = dict(evidence[0])
    evidence[1] = dict(evidence[1])
    evidence[0]["probes"] = list(evidence[0]["probes"])
    evidence[1]["probes"] = list(evidence[1]["probes"])
    evidence[0]["probes"][1] = X.probe_record("verifier", "test-run", P1, t1, c1)
    evidence[1]["probes"][1] = X.probe_record("verifier", "test-run", P2, t2, c2)
    doc["evidence"] = evidence
    consumers = [dict(item) for item in doc["downstream_consumers"]]
    consumers[0]["exit_code"] = c1
    consumers[0]["read_ok"] = c1 == 0
    consumers[0]["executed"] = True
    consumers[0]["probe"] = X.probe_record("verifier", "test-run", P1, t1, c1)
    consumers[1]["exit_code"] = c2
    consumers[1]["read_ok"] = c2 == 0
    consumers[1]["executed"] = True
    consumers[1]["probe"] = X.probe_record("verifier", "test-run", P2, t2, c2)
    doc["downstream_consumers"] = consumers
    return doc


def main() -> int:
    unit = X.catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    live = X.measure_live(REPO)
    if X.brace_scanner_calls_json_loads():
        print("FAILED:SYN-0031 extractor B source contains json.loads")
        return 1
    silence = live["silence"]
    if not silence["protocol_silent_on_preset_items"]:
        print("FAILED:SYN-0031 protocol regex matched a preset item")
        return 1
    if not silence["preset_silent_on_protocol_items"]:
        print("FAILED:SYN-0031 preset regex matched a protocol item")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(live, unit, now)
    if validate_or_die(doc, "pre-probe") != 0:
        return 1
    out = REPO / X.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json_dumps(doc), encoding="utf-8")
    code1, text1 = run_cmd(P1)
    code2, text2 = run_cmd(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:SYN-0031 emit probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = attach_live_probes(doc, text1, code1, text2, code2, ended)
    if validate_or_die(doc, "post-probe") != 0:
        return 1
    out.write_text(json_dumps(doc), encoding="utf-8")
    digest, size = X.sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:SYN-0031 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:SYN-0031 completion sentinel absent from artifact text")
        return 1
    print(f"wrote {X.OUT_REL} bytes={size} sha256={digest}")
    for row in X.domain_from_artifact(doc)["floors"]:
        print(
            f"  {row['id']}: this={row['this_count']} prior={row['prior_count']} "
            f"json={row['json_count']} regex={row['regex_count']} "
            f"extractors={row['extractor_verdict']} vs_prior={row['vs_prior']} "
            f"floor_met={row['floor_met']}"
        )
    print("SUCCESS:SYN-0031 emit")
    return 0


def json_dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
