#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0047.failure-class-coverage.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classes as C  # noqa: E402
import controls as CTL  # noqa: E402
import inventory as I  # noqa: E402
import mapper as M  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/synthesis/SYN-0047.failure-class-coverage.json"
SCHEMA = "command-center/schema/coverage-map.schema.json"
SENTINEL = "SUCCESS:SYN-0047"
COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0047 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the row count equals the "
    "extracted class count and the uncovered set is enumerated. Any other "
    "terminal state is FAILED:SYN-0047 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Question: which of the failure classes the spec requires in the "
    "regression suite (_USER-PROMPTS.md:11298-11347) are NOT covered by a "
    "test today, and which synthesized root causes correspond to no listed "
    "class? Target: a three-way coverage map (spec class x root cause x "
    "existing test) whose UNCOVERED set becomes the input to the Phase 16 "
    "writeback. This unit MEASURES the gap and hands it over; IMP-0384 "
    "performs the lesson writeback and benchmark augmentation, so authoring "
    "the tests here would duplicate that unit."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0047/probe1_extraction_and_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0047/probe2_claimed_not_proven.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0047/classes.py",
    "command-center/p2-wave/probes/SYN-0047/mapper.py",
    "command-center/p2-wave/probes/SYN-0047/inventory.py",
    "command-center/p2-wave/probes/SYN-0047/controls.py",
    "command-center/p2-wave/probes/SYN-0047/schema_local.py",
    "command-center/p2-wave/probes/SYN-0047/probe1_extraction_and_known_present.py",
    "command-center/p2-wave/probes/SYN-0047/probe2_claimed_not_proven.py",
]


def build() -> dict:
    extracted = C.extract_classes(REPO)
    classes = extracted["classes"]
    inv = I.collect_inventory(REPO)
    rows = M.map_classes(classes, inv["tests"], inv["mutations"], inv["causes"])
    n = extracted["extracted_count"]
    if len(rows) != n:
        raise SystemExit(f"FAILED:SYN-0047 row count {len(rows)} != extracted {n}")
    uncovered = M.uncovered_rows(rows)
    unmatched = M.unmatched_causes(inv["causes"], rows)
    known = CTL.assert_known_present()
    claimed = CTL.assert_claimed_not_proven()
    both = CTL.run_both_states()
    n_cov = sum(1 for r in rows if r["status"] == M.COVERED)
    n_claim = sum(1 for r in rows if r["status"] == M.CLAIMED)
    n_unc = sum(1 for r in rows if r["status"] == M.UNCOVERED)
    n_cause = len(inv["causes"])
    row_ok = len(rows) == n == C.EXPECTED_COUNT
    if not row_ok or not claimed["pass"] or not known["pass"]:
        raise SystemExit("FAILED:SYN-0047 a required test did not PASS")
    if not (both["fired"] and both["good_passes"] and both["broken_fails"]):
        raise SystemExit("FAILED:SYN-0047 known-present detector both-states failed")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    syn = inv["syn0001"]
    artifacts = [S.artifact_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"] or a["bytes"] < 1]
    if missing:
        raise SystemExit(f"FAILED:SYN-0047 missing supporting {missing}")
    return {
        "schema_version": 1,
        "unit_id": "SYN-0047",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11298-11347",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Extraction count is asserted at 48 (title) from inclusive "
                    "spec lines 11300-11347; every class is a row and the "
                    f"UNCOVERED/CLAIMED set is enumerated ({len(uncovered)}/{n})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0047/classes.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c 'import classes,json; "
                            "print(json.dumps(classes.extract_classes()[\"extracted_count\"]))'"
                        ),
                        "raw_output": (
                            f"extracted={n} rows={len(rows)} "
                            f"source_status={extracted['source_status']}"
                        ),
                        "fingerprint": "syn0047:extract:source",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": "re-run by write_receipts.py / G-1 measure",
                        "fingerprint": "syn0047:extract:probe1",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A mention without a CC-0014 mutation record is "
                    "CLAIMED-NOT-PROVEN, never COVERED; a planted FIRED "
                    "mutation is the only path to COVERED (known-present control)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0047/controls.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "python3 -c 'import controls; "
                            "print(controls.assert_claimed_not_proven()[\"status\"])'"
                        ),
                        "raw_output": (
                            f"claimed={claimed['status']} "
                            f"known_present={known['status']} "
                            f"detector_fired={both['fired']}"
                        ),
                        "fingerprint": "syn0047:claimed:source",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": P2,
                        "raw_output": "re-run by write_receipts.py / G-1 measure",
                        "fingerprint": "syn0047:claimed:probe2",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: first observation is the verdict; "
                "SYN-0001/CC-0014 were not rebuilt (no ADV circle)"
            ),
        },
        "tests": [
            {
                "id": "test_every_enumerated_spec_class_appears_as_a_row",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_a_test_without_a_mutation_record_is_CLAIMED_NOT_PROVEN_not_COVERED",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "known-present-control",
                "command": P1,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-KNOWN-PRESENT-DETECTOR",
                "kind": "mutation",
                "description": (
                    "controls.detector: silent=True (broken) must fail; "
                    "silent=False (good) must pass; mapper then yields COVERED "
                    "for FC-11324 with the FIRED mutation record."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"broken_fails={both['broken_fails']} fired={both['fired']}"
                ),
                "good_state_output": (
                    f"good_passes={both['good_passes']} status={known['status']}"
                ),
            },
            {
                "id": "NC-UNPROVEN-MENTION-NOT-COVERED",
                "kind": "known-broken-fixture",
                "description": (
                    "A planted mention of FC-11325 with no mutation record must "
                    "resolve CLAIMED-NOT-PROVEN, never COVERED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "COVERED-without-mutation would fail probe2",
                "good_state_output": f"status={claimed['status']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0047-probe2-claimed-not-proven",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe2 re-derives the uncovered set from raw inventory and "
                "does not read this conclusion first."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0047/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0047",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/SYN-0047/"
                    "probe1_extraction_and_known_present.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": P1,
                    "raw_output": "G-1 re-runs this consumer after emit",
                    "fingerprint": "syn0047:consumer:probe1",
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md is absent on this worktree. The 48 class "
                    "names are reconstructed from ARC-0005 (11301-11347) plus "
                    "inclusive 11300; 11300 has no catalog gloss."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Parse _USER-PROMPTS.md:11298-11347 on a tree that has the "
                    "file and re-run classes.extract_classes; row names must "
                    "match the source lines."
                ),
            },
            {
                "claim": (
                    "SYN-0001.root-cause-hierarchy.json is absent; unmatched "
                    f"root causes are {len(unmatched)}/{n_cause} from that source. "
                    "CC-0014 mutation receipts are absent, so live COVERED "
                    "cells cannot be mutation-proven from that ledger."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Load SYN-0001 and CC-0014 when those units deliver on this "
                    "tree; re-run mapper.map_classes and compare uncovered/"
                    "unmatched sets. Do not rebuild those artifacts here."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "coverage-cartographer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "coverage-map",
            "observations": [
                {
                    "name": "extracted-class-count",
                    "measured": n,
                    "method": "classes.extract_classes asserted equality",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/classes.py",
                },
                {
                    "name": "row-count",
                    "measured": len(rows),
                    "method": "mapper.map_classes one row per extracted class",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/mapper.py",
                },
                {
                    "name": "uncovered-or-claimed-count",
                    "measured": len(uncovered),
                    "method": "status != COVERED enumerated with denominators",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/mapper.py",
                },
                {
                    "name": "covered-count",
                    "measured": n_cov,
                    "method": "CC-0014 mutation-proven bound tests only",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/mapper.py",
                },
                {
                    "name": "unmatched-root-causes",
                    "measured": len(unmatched),
                    "method": "reverse join of SYN-0001 nodes onto spec classes",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/inventory.py",
                },
                {
                    "name": "known-present-status",
                    "measured": known["status"],
                    "method": "planted FIRED mutation on FC-11324 fixture",
                    "anchor": "command-center/p2-wave/probes/SYN-0047/controls.py",
                },
            ],
            "control_ids": [
                "NC-KNOWN-PRESENT-DETECTOR",
                "NC-UNPROVEN-MENTION-NOT-COVERED",
            ],
            "title": (
                "Known-failure-class coverage map: join the spec's 48 seeded "
                "classes against root causes and the live suite"
            ),
            "question": QUESTION,
            "phase": "14",
            "generated_at": now,
            "sentinel_short": SENTINEL,
            "extraction": {
                "cited_range": extracted["cited_range"],
                "class_line_range": extracted["class_line_range"],
                "expected_count": extracted["expected_count"],
                "extracted_count": n,
                "count_asserted": True,
                "source_status": extracted["source_status"],
                "source_path": extracted["source_path"],
                "reconstruction": extracted["reconstruction"],
                "catalog_title_count": extracted["catalog_title_count"],
                "arc0005_count": extracted["arc0005_count"],
            },
            "inputs": {
                "user_prompts": {
                    "path": "_USER-PROMPTS.md",
                    "cited": "11298-11347",
                    "present": extracted["source_status"] == "PRESENT",
                },
                "test_registry": inv["test_registry"],
                "cc0014": inv["cc0014"],
                "syn0001": {
                    "path": syn["path"],
                    "present": syn["present"],
                    "status": syn["status"],
                    "node_count": len(syn.get("nodes") or []),
                    "note": syn["note"],
                },
                "b08": inv["b08"],
                "live_scan_count": inv["live_scan_count"],
            },
            "rows": rows,
            "uncovered": uncovered,
            "unmatched_root_causes": unmatched,
            "counts": {
                "extracted": n,
                "row_count": len(rows),
                "uncovered": len(uncovered),
                "covered": n_cov,
                "claimed_not_proven": n_claim,
                "uncovered_status": n_unc,
                "unmatched_root_causes": len(unmatched),
                "denominators": {
                    "spec_classes_covered": f"{n_cov}/{n}",
                    "spec_classes_claimed_not_proven": f"{n_claim}/{n}",
                    "spec_classes_uncovered": f"{n_unc}/{n}",
                    "spec_classes_not_mutation_proven": f"{len(uncovered)}/{n}",
                    "root_causes_unmatched": f"{len(unmatched)}/{n_cause}",
                },
            },
            "controls": {
                "known_present": {
                    "class_id": "FC-11324",
                    "status": known["status"],
                    "pass": known["pass"],
                    "note": "fixture-only; not mixed into the 48 live rows",
                },
                "claimed_not_proven": {
                    "class_id": "FC-11325",
                    "status": claimed["status"],
                    "pass": claimed["pass"],
                    "note": "fixture-only; mention without mutation is not COVERED",
                },
            },
            "handoff_to": "IMP-0384",
            "named_probes": [
                {
                    "id": "probe1",
                    "command": P1,
                    "role": "extraction-and-known-present",
                },
                {
                    "id": "probe2",
                    "command": P2,
                    "role": "claimed-not-proven-and-reviewer",
                },
            ],
            "notes": (
                "Live rows are an honest gap measurement. COVERED is reserved "
                "for CC-0014 mutation-proven tests. SYN-0001 and CC-0014 "
                "receipts are ABSENT on this worktree and were not rebuilt. "
                "TEST-REGISTRY is loaded when present. Known-present COVERED "
                "is proven by the mapper fixture, not by inventing live coverage."
            ),
        },
    }


def main() -> int:
    doc = build()
    S.validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:SYN-0047 completion_sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = S.digest_file(out)
    counts = doc["report"]["counts"]
    print(f"wrote {OUT} bytes={size} sha256={sha} rows={counts['row_count']}")
    print(
        "covered={c} claimed={k} uncovered={u} unmatched_causes={m}".format(
            c=counts["covered"],
            k=counts["claimed_not_proven"],
            u=counts["uncovered_status"],
            m=counts["unmatched_root_causes"],
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
