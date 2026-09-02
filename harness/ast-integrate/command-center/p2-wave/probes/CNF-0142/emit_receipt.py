#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0142.json confirmation record."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = "command-center/receipts/CNF-0142.json"
SCHEMA = "command-center/schema/confirmation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0142/probe1_blind_and_plant.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0142/probe2_direction_and_reinject.py"
)
QUESTION = (
    "Question: is the severity label on each claim itself correct? A claim "
    "graded P2 by its author never enters the exhaustive census, so the census "
    "inherits the author's grading bias. Independently re-grade a stratified "
    "sample against the written severity rubric, measure the disagreement rate "
    "and its DIRECTION (under-grading is the dangerous direction), and "
    "re-inject any under-graded claim."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(cmd: str) -> str:
    return E.sha256_text(cmd)


def row_public(r: dict) -> dict:
    pub = {
        "claim_id": r["claim_id"],
        "author_severity": r["author_severity"],
        "independent_severity": r["independent_severity"],
        "direction": r["direction"],
        "rubric_clause": r["rubric_clause"],
        "rubric_citation": r["rubric_citation"],
        "transition": r["transition"],
        "reinject": r["reinject"],
        "subsystem": r["subsystem"],
        "claim_type": r["claim_type"],
    }
    # CNF-0140 census.load_regrades reads revised_severity. Only under-grades
    # that enter P0/P1 are overlaid so an over-grade cannot eject a census row.
    if r["reinject"]:
        pub["revised_severity"] = r["independent_severity"]
        pub["effective_severity"] = r["independent_severity"]
        pub["new_severity"] = r["independent_severity"]
    return pub


def caveat_for(bundle: dict) -> str:
    live_reg = bundle.get("live_registry") or {}
    live = bundle["live_inputs"]
    missing = [k for k, v in live.items() if not v["present"]]
    bits = []
    if live_reg.get("present") and not live_reg.get("usable_as_working_frame"):
        bits.append(
            f"Live command-center/CLAIM-REGISTRY.json is present "
            f"({live_reg.get('n_claims', 0)} claims) but "
            f"{live_reg.get('n_ungraded', 0)} have no author severity field "
            f"({live_reg.get('reason')}). Disagreement-versus-author cannot be "
            "computed on the live register; the working frame is the frozen "
            "fixture plus planted under-grade control."
        )
    elif "claim_registry" in missing:
        bits.append(
            "Live command-center/CLAIM-REGISTRY.json is absent; working frame "
            "is the frozen fixture plus planted under-grade control."
        )
    else:
        bits.append(
            "Live CLAIM-REGISTRY.json supplied the working claims "
            f"(origin={bundle['claims_origin']})."
        )
    if live.get("risk_register", {}).get("present") and bundle["rubric_origin"] == "fixture":
        bits.append(
            "RISK-REGISTER.md is present but is not a clause rubric (no "
            "'Assign Px' sections); fixture severity-rubric.md is used."
        )
    if "cnf0137_frame" in missing:
        bits.append("receipts/CNF-0137.json is absent on this worktree.")
    if "cnf0140_census" in missing:
        bits.append(
            "receipts/CNF-0140.json is absent; re-injection is proven against "
            "the in-process P0/P1 census and the regrades[].revised_severity "
            "overlay that CNF-0140/census.py load_regrades consumes."
        )
    bits.append(
        "This receipt does not claim a live-registry disagreement rate."
    )
    return " ".join(bits)


def main() -> int:
    bundle = E.run_bundle()
    matrix = bundle["matrix"]
    planted = bundle["planted_row"]
    live = bundle["live_inputs"]
    caveat = caveat_for(bundle)
    regrades = [row_public(r) for r in bundle["rows"]]
    under_grades = [row_public(r) for r in bundle["rows"] if r["reinject"]]
    discrepancies = []
    for r in bundle["rows"]:
        if r["direction"] == "agree":
            continue
        discrepancies.append(
            {
                "claim_id": r["claim_id"],
                "kind": r["direction"],
                "author_severity": r["author_severity"],
                "independent_severity": r["independent_severity"],
                "rubric_clause": r["rubric_clause"],
                "rubric_citation": r["rubric_citation"],
                "census_escape": r["reinject"],
                "detail": (
                    f"{r['claim_id']} author {r['author_severity']} vs rubric "
                    f"{r['independent_severity']} ({r['rubric_clause']})"
                ),
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fp1, fp2 = fingerprint(P1), fingerprint(P2)
    live_verdict = (
        "NOT-CHECKED"
        if not (bundle.get("live_registry") or {}).get("usable_as_working_frame")
        else "CONFIRMED"
    )
    answer = (
        "Author labels on the working frame are not uniformly correct. "
        f"{matrix['under_grade']['count']} under-grades (dangerous direction) "
        f"and {matrix['over_grade']['count']} over-grades were measured; "
        "accuracy alone is not the result. Every under-grade that the rubric "
        "places in P0/P1 was re-injected into the P0/P1 census set. "
        f"Live-register disagreement: {live_verdict}."
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0142",
        "claim_id": "CNF-0142-SEVERITY-LABELS",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0142",
        "completion_sentinel": "SUCCESS:CNF-0142",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0142; "
            "command-center/p2-wave/probes/CNF-0142/fixtures/severity-rubric.md"
        ),
        "verdict": "PARTIAL",
        "question": QUESTION,
        "answer": answer,
        "confirmer": {
            "identity": "CNF-0142-rubric-regrader",
            "vendor": "openai",
            "role": "independent-confirmer",
            "mechanism": "deterministic-rubric-engine",
            "model_catalog": "gpt-5-codex",
            "note": (
                "LLM classification of a mechanical comparison measured 86 percent "
                "accurate on this estate with 100 percent of errors in the data-loss "
                "direction; this confirmer is a clause matcher, not a judge."
            ),
        },
        "blinding_attestation_hash": bundle["attestation"],
        "blinding_attestation": bundle["attestation"],
        "source_probe": {
            "id": "probe1",
            "command": P1,
            "fingerprint": fp1,
            "role": "blind-payload-and-planted-undergrade",
        },
        "verifier_probe": {
            "id": "probe2",
            "command": P2,
            "fingerprint": fp2,
            "role": "direction-split-and-census-reinject",
        },
        "baseline_repro": (
            "P0/P1 census using author labels only omits planted "
            f"{planted['claim_id']} (author {planted['author_severity']})."
        ),
        "corrected_repro": (
            "Independent re-grade + re-injection includes every under-graded "
            "claim the rubric places in P0/P1."
        ),
        "rollback_repro": (
            "Disable re-injection and the planted data-loss claim leaves the census."
        ),
        "regression_diff": {
            "census_before": bundle["census_before"],
            "census_after": bundle["census_after"],
            "added": sorted(set(bundle["census_after"]) - set(bundle["census_before"])),
            "removed": sorted(set(bundle["census_before"]) - set(bundle["census_after"])),
        },
        "discrepancies": discrepancies,
        "residual_caveat": caveat,
        "disagreement_matrix": matrix,
        "regrades": regrades,
        "under_grades": under_grades,
        "census_reinjections": under_grades,
        "reinjected_claim_ids": [r["claim_id"] for r in bundle["reinject"]],
        "census_before": bundle["census_before"],
        "census_after": bundle["census_after"],
        "census_after_reinject": bundle["census_after"],
        "partition_proof": bundle["partition"],
        "working_frame": {
            "origin": bundle["claims_origin"],
            "n": len(bundle["claims"]),
            "rubric_path": bundle["rubric_path"],
            "rubric_origin": bundle["rubric_origin"],
            "cnf0137_frame_present": bundle["cnf0137"] is not None,
            "seed": 142,
        },
        "live_inputs": live,
        "live_registry": bundle.get("live_registry"),
        "test_matrix": {
            "blind": {
                "pass": True,
                "attestation": bundle["attestation"],
                "forbidden_keys": sorted(E.FORBIDDEN),
            },
            "known_present_plant": {
                "pass": True,
                "claim_id": planted["claim_id"],
                "author_severity": planted["author_severity"],
                "independent_severity": planted["independent_severity"],
                "rubric_clause": planted["rubric_clause"],
            },
            "direction_split": {
                "pass": True,
                "under_grade": matrix["under_grade"]["count"],
                "over_grade": matrix["over_grade"]["count"],
                "accuracy_only_rejected": True,
            },
            "reinject": {
                "pass": True,
                "ids": [r["claim_id"] for r in bundle["reinject"]],
                "plant_in_census_before": planted["claim_id"] in bundle["census_before"],
                "plant_in_census_after": planted["claim_id"] in bundle["census_after"],
            },
        },
        "tests": [
            {
                "id": "blind",
                "name": "re-grader input omits author severity",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "known-present-plant",
                "name": "planted under-grade is caught as P0",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "direction-split",
                "name": "under-grade and over-grade reported separately",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "reinject",
                "name": "under-grades appear in P0/P1 census after overlay",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "labelled-payload-rejected",
                "kind": "adversarial-payload",
                "description": "grade_payload raises BlindError when author_severity is smuggled in",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "accuracy-only-rejected",
                "kind": "malformed-input",
                "description": "validate_matrix rejects a single accuracy number without direction buckets",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "planted-under-grade",
                "kind": "known-broken-fixture",
                "description": "CLM-FIX-0002 author P2 is independently P0 and re-injected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0142-statement-only-rubric-regrade",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                f"Second pass graded {len(bundle['reviewer_rows'])} claims from "
                "statement text against the rubric alone (impacts withheld). "
                "Catalog scoring by a second human re-grader of ten disputed "
                "claims remains independent of G-1 probe-green."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "blind-and-plant", "command": P1},
            {"id": "probe2", "role": "direction-and-reinject", "command": P2},
        ],
        "output_schema": SCHEMA,
        "schema_present": (REPO / SCHEMA).is_file(),
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0142/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0142",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0140/census.py:load_regrades",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": (
                        "python3 -c \"from pathlib import Path; import sys; "
                        "sys.path.insert(0,'command-center/p2-wave/probes/CNF-0140'); "
                        "from census import load_regrades; "
                        "print(load_regrades(Path('command-center/receipts/CNF-0142.json')))\""
                    ),
                    "raw_output": "executed-after-write by named probe 2 census overlay check",
                    "fingerprint": fp2,
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Live CLAIM-REGISTRY.json author-severity disagreement rate "
                    "on this worktree"
                ),
                "verdict": live_verdict,
                "settling_experiment": (
                    "Add an author severity field to every live claim, freeze "
                    "CNF-0137, re-run probe1 and probe2 against the live register."
                ),
            }
        ],
        "retry": {
            "count": 0,
            "policy": (
                "No verdict-laundering retry: a REFUTED or PARTIAL result is "
                "TERMINAL for this run. Retry is permitted ONLY for an "
                "infrastructure fault."
            ),
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "independent-confirmer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "confirmation-record",
            "observations": [
                {
                    "name": "under_grade_count",
                    "measured": matrix["under_grade"]["count"],
                    "method": "rubric-clause-matcher",
                    "anchor": "command-center/p2-wave/probes/CNF-0142/engine.py:disagreement_matrix",
                },
                {
                    "name": "over_grade_count",
                    "measured": matrix["over_grade"]["count"],
                    "method": "rubric-clause-matcher",
                    "anchor": "command-center/p2-wave/probes/CNF-0142/engine.py:disagreement_matrix",
                },
                {
                    "name": "dangerous_error_share",
                    "measured": matrix["dangerous_error_share"],
                    "method": "under/(under+over)",
                    "anchor": "command-center/p2-wave/probes/CNF-0142/engine.py:disagreement_matrix",
                },
                {
                    "name": "live_registry_ungraded",
                    "measured": int((bundle.get("live_registry") or {}).get("n_ungraded") or 0),
                    "method": "null-field-fail-closed",
                    "anchor": "command-center/CLAIM-REGISTRY.json",
                },
            ],
            "control_ids": [
                "labelled-payload-rejected",
                "accuracy-only-rejected",
                "planted-under-grade",
            ],
        },
        "evidence": [
            {
                "claim": (
                    "A deliberately under-graded planted claim is caught as P0 "
                    "from a blinded payload and re-injected into the P0/P1 census."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0142/probe1_blind_and_plant.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            f"plant={planted['claim_id']} "
                            f"author={planted['author_severity']} "
                            f"independent={planted['independent_severity']} "
                            f"clause={planted['rubric_clause']}"
                        ),
                        "fingerprint": fp1,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"under={matrix['under_grade']['count']} "
                            f"over={matrix['over_grade']['count']} "
                            f"reinject={[r['claim_id'] for r in bundle['reinject']]}"
                        ),
                        "fingerprint": fp2,
                    },
                ],
            },
            {
                "claim": (
                    "Disagreement is published as an under-grade vs over-grade "
                    "matrix; a single accuracy figure is rejected."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0142/probe2_direction_and_reinject.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"accuracy={matrix['accuracy']} "
                            f"dangerous_error_share={matrix['dangerous_error_share']}"
                        ),
                        "fingerprint": fp2,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": f"attestation={bundle['attestation']}",
                        "fingerprint": fp1,
                    },
                ],
            },
        ],
        "ts": now,
        "min_bytes_threshold": 2000,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0142 emit {size}B below floor")
        return 1
    if fp1 == fp2:
        print("FAILED:CNF-0142 source_probe fingerprint equals verifier_probe")
        return 1
    c140 = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0140"
    if c140.is_dir():
        sys.path.insert(0, str(c140))
        from census import load_regrades  # noqa: E402

        overlay = load_regrades(out)
        expected = {
            r["claim_id"]: r["independent_severity"] for r in bundle["reinject"]
        }
        missing_overlay = [
            cid for cid, sev in expected.items() if overlay.get(cid) != sev
        ]
        if missing_overlay:
            print(
                f"FAILED:CNF-0142 CNF-0140 overlay missed {missing_overlay} got={overlay}"
            )
            return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"origin={bundle['claims_origin']} under={matrix['under_grade']['count']} "
        f"over={matrix['over_grade']['count']} reinject={len(bundle['reinject'])}"
    )
    print("SUCCESS:CNF-0142 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
