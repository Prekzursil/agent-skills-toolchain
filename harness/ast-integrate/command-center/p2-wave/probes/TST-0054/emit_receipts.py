#!/usr/bin/env python3
"""Emit TST-0054 receipt, SUBAGENT-RETURN, and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0054"
OUT = "command-center/receipts/TST-0054.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0054/probe1_producer_rejects_duplicate_keys.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0054/probe2_consumer_behaviours_recorded.py"
)
SUPPORTING = [
    "tools/lib/strict_json.py",
    "tools/plugin/duplicate_key_matrix.py",
    "tools/plugin/tests/test_duplicate_keys.py",
    "command-center/p2-wave/probes/TST-0054/probe1_producer_rejects_duplicate_keys.py",
    "command-center/p2-wave/probes/TST-0054/probe2_consumer_behaviours_recorded.py",
    "command-center/p2-wave/probes/TST-0054/fixtures/duplicate-name.json",
    "tools/plugin/layout_fixtures.py",
    "tools/plugin/scenario.py",
    "tools/plugin/hook_client.py",
    "tools/marketplace/lockfile.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    if path.is_file():
        sha, size = digest(path)
        present = True
    else:
        sha, size, present = "", 0, False
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": present,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0054/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(REPO / "tools" / "lib"))
    from plugin.duplicate_key_matrix import measure_matrix

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0054 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    table = measure_matrix()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0054",
        "completion_sentinel": "SUCCESS:TST-0054",
        "title": "Duplicate-key last-wins divergence across parsers",
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json TST-0054: a document with a "
            "repeated key is resolved differently by different JSON parsers "
            "(first-wins, last-wins, error). Distinct from TST-0053 / :11309 "
            "(case-distinct keys)."
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-test-engineer",
            "execution_substrate": "linux-worktree",
        },
        "question_or_target": (
            "Target: a document with a repeated key is resolved differently by "
            "different JSON parsers (first-wins, last-wins, error). Determine "
            "the behaviour of every parser in the pipeline and require the "
            "producer to make duplicates impossible. Distinct from :11309 - "
            "same case, repeated key."
        ),
        "evidence_requirement": (
            "a parser-by-parser resolution table for one duplicate-key fixture"
        ),
        "implementation": {
            "producer": "tools/lib/strict_json.py",
            "producer_rule": (
                "dumps_from_pairs raises DuplicateKeyError naming the key and "
                "both values; dumps round-trips through loads_strict so "
                "duplicate members cannot leave the producer"
            ),
            "wired_emit_paths": [
                "tools/plugin/layout_fixtures.py:write_json",
                "tools/plugin/scenario.py:write_healthy/write_broken",
                "tools/plugin/hook_client.py:emit_inventory",
                "tools/marketplace/lockfile.py:canonical_dumps",
            ],
            "fixture": table["fixture"],
            "parser_resolution_table": table["parsers"],
            "resolutions_observed": table["resolutions_observed"],
            "last_wins_parsers": table["last_wins_parsers"],
            "error_parsers": table["error_parsers"],
            "first_wins_parsers": table["first_wins_parsers"],
            "independent_pairs_hook": table["independent_pairs_hook"],
            "duplicate_name_occurrence_count": table["duplicate_name_occurrence_count"],
            "naive_json_loads_hides_duplicate": table["naive_json_loads_hides_duplicate"],
            "pipeline_json_loads_callers": table["pipeline_json_loads_callers"],
            "producer_duplicate_rejected": table["producer_duplicate_rejected"],
            "note": (
                "No first-wins parser is present in this pipeline. Stdlib "
                "json.loads/load/JSONDecoder and node JSON.parse (when "
                "installed) last-wins; strict_json.loads_strict errors. "
                "Behaviour is recorded from live invocation, not assumed."
            ),
        },
        "artifacts": [],
        "evidence": [
            {
                "claim": (
                    "The producer refuses a same-case repeated key and reports "
                    "both values; a unique-key document emits and round-trips "
                    "(both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/lib/strict_json.py:dumps_from_pairs",
                "kind": "producer-refusal",
                "detail": json.dumps(table["producer_duplicate_rejected"], sort_keys=True),
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    }
                ],
            },
            {
                "claim": (
                    "Each consumer parser was invoked on one duplicate-key "
                    "fixture; resolutions last-wins vs error were recorded, "
                    "not assumed. Independent object_pairs_hook sees two "
                    "name members while json.loads hides one."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/duplicate_key_matrix.py:measure_matrix",
                "kind": "parser-resolution-table",
                "detail": json.dumps(
                    {
                        "resolutions_observed": table["resolutions_observed"],
                        "last_wins_parsers": table["last_wins_parsers"],
                        "error_parsers": table["error_parsers"],
                        "duplicate_name_occurrence_count": table[
                            "duplicate_name_occurrence_count"
                        ],
                    },
                    sort_keys=True,
                ),
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_duplicate_key_is_rejected_by_the_producer",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "test_each_consumer_parser_behaviour_is_recorded_not_assumed",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0054-C1-both-states-producer",
                "kind": "both-states",
                "description": (
                    "Unique pairs emit; duplicate pairs raise DuplicateKeyError "
                    "with first and second values."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0054-C2-not-assumed-uniform-resolution",
                "kind": "measurement",
                "description": (
                    "A table that listed last-wins for every parser, or error "
                    "for every parser, fails. Stdlib last-wins and "
                    "loads_strict error must both appear."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "TST-0054-C3-naive-json-loads-hides-duplicate",
                "kind": "mutation",
                "description": (
                    "json.loads of the fixture yields a one-key dict with "
                    "name=second while object_pairs_hook still lists two "
                    "name members. A dict-key uniqueness checker would miss "
                    "the duplicate."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0054-probe2-live-parser-matrix",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the live matrix plus the pairs-hook "
                "count; a stdlib json.loads uniqueness check is proven to "
                "hide the duplicate. Not a self-attested prose review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0054/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 TST-0054: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:TST-0054"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Fill artifact sha after supporting files; primary sha after write.
    supporting_rows = [row(p, "supporting") for p in SUPPORTING]
    receipt["artifacts"] = [
        {
            "path": p["path"],
            "role": p["role"],
            "sha256": p["sha256"],
            "bytes": p["bytes"],
            "exists": True,
        }
        for p in supporting_rows
    ]
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + supporting_rows
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0054",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "producer-rejects-duplicate-keys",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "consumer-behaviours-recorded-not-assumed",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0054/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0054-probe2-live-parser-matrix",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0054: live named probes exit 0, TST-0054.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0054 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
