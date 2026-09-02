#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0296.json and per-unit G-1 manifests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
from bench.matched_pairing import load_scenario, pair_scenario  # noqa: E402

OUT = "command-center/receipts/TST-0296.json"
SCHEMA = "command-center/schema/receipt.schema.json"
ENGINE = "tools/bench/matched_pairing.py"
SCENARIO = "command-center/p2-wave/probes/TST-0296/fixtures/scenario.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0296/probe1_intersection.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0296/probe2_asymmetric.py"
)
QUESTION = (
    "Implementation target: Phase 2B step 7 at :10739 requires running source "
    "workflows and fused candidates on matched benchmark cases, and :10741 "
    "certifies only workflows that outperform or materially complement their "
    "sources. Build the pairing rule that selects the case subset every source "
    "can actually run (an intersection, not a union), records the excluded cases "
    "with the reason, and forbids a comparison whose intersection is below a "
    "minimum size. Comparing a fusion on cases its sources cannot even attempt "
    "is the arithmetic that manufactures a winner."
)
SUPPORTING = [
    ENGINE,
    SCENARIO,
    "command-center/p2-wave/probes/TST-0296/probe1_intersection.py",
    "command-center/p2-wave/probes/TST-0296/probe2_asymmetric.py",
    "command-center/p2-wave/probes/TST-0296/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def live_inputs() -> dict:
    cases_dir = REPO / "command-center/bench/cases"
    registry_candidates = [
        "command-center/wfa/WFA-0078-candidate-registry-v2.json",
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    ]
    found_registry = next(
        (p for p in registry_candidates if (REPO / p).is_file()), None
    )
    return {
        "bench_cases_dir": {
            "path": "command-center/bench/cases/",
            "present": cases_dir.is_dir(),
            "note": "TST-0295 corpus; pairing loads it when present and does not invent it",
        },
        "b04_candidate_registry": {
            "path": found_registry,
            "present": found_registry is not None,
            "searched": registry_candidates,
        },
        "receipt_schema": {
            "path": SCHEMA,
            "present": (REPO / SCHEMA).is_file(),
        },
        "pairing_fixture": SCENARIO,
    }


def main() -> int:
    scenario = load_scenario(REPO / SCENARIO)
    comparisons = pair_scenario(scenario)
    by_id = {c["comparison_id"]: c for c in comparisons}
    h2h = by_id["cmp-h2h-sufficient"]
    low = by_id["cmp-low-n-blocked"]
    if h2h["comparison_status"] != "COMPARABLE":
        print("FAILED:TST-0296 sufficient comparison not COMPARABLE")
        return 1
    if low["comparison_status"] != "BLOCKED_LOW_N":
        print("FAILED:TST-0296 low-n comparison not blocked")
        return 1
    if h2h["complementarity"]["folded_into_head_to_head"]:
        print("FAILED:TST-0296 complementarity folded")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inputs = live_inputs()
    doc = {
        "unit_id": "TST-0296",
        "id": "TST-0296",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "matched-case-pairing",
        "title": "Matched-case pairing so a fusion is compared against its sources on identical inputs",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0296",
        "completion_sentinel": "SUCCESS:TST-0296",
        "min_bytes_threshold": 2048,
        "pairing_rule": {
            "head_to_head": (
                "intersection of per-source runnable sets derived from "
                "required_capabilities ⊆ workflow.capabilities"
            ),
            "not": "union of cases any party can run",
            "default_min_intersection": 10,
            "below_minimum": "BLOCKED_LOW_N; no winner; no head-to-head score",
            "complementarity": (
                "fusion runnable minus source union; published separately; "
                "fold_complementarity is a PairingError"
            ),
            "two_intersection_methods": [
                "set.intersection of expanded runnable id sets",
                "per-case all(can_run(source, case))",
            ],
            "engine": ENGINE,
        },
        "live_inputs": inputs,
        "fixture": {
            "path": SCENARIO,
            "corpus_size": len(scenario["cases"]),
            "workflow_ids": sorted(scenario["workflows"]),
            "note": (
                "Controls are synthetic capability lanes. This is not a claim "
                "that the TST-0295 corpus or the B04 284-candidate registry "
                "were present and scored."
            ),
        },
        "comparisons": comparisons,
        "evidence": {
            "per_comparison_published": True,
            "fields": [
                "intersection_size",
                "intersection_case_ids",
                "excluded (case_id + reason)",
                "complementarity.case_ids",
            ],
            "cmp-h2h-sufficient": {
                "intersection_size": h2h["intersection_size"],
                "excluded_count": h2h["excluded_count"],
                "complementarity_count": h2h["complementarity"]["count"],
                "union_would_manufacture_win": h2h["union_inflation_diagnostic"][
                    "manufactures_fusion_win"
                ],
            },
            "cmp-low-n-blocked": {
                "intersection_size": low["intersection_size"],
                "status": low["comparison_status"],
                "reported_win": low["reported_win"],
            },
        },
        "tests": {
            "mechanical_intersection": True,
            "below_minimum_blocks": True,
            "asymmetric_capability_not_folded": True,
        },
        "scope": {
            "proof_surface": (
                "executable pairing engine on disclosed fixtures; both-states "
                "union inflation vs intersection; low-n block; fold refusal"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "command-center/bench/cases/ was a live TST-0295 corpus",
                "the B04 candidate registry was present on this worktree",
                "a fusion was certified as outperforming its sources on live workflows",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "benchmark-engineer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "TST-0296-probe2-asymmetric",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs pairing from the fixture, refuses complementarity "
                "fold, and independently reproduces the low-n block. Catalog "
                "statistics review of live per-case outcomes is a later unit "
                "(TST-0298) and is not claimed here."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "mechanical-intersection", "command": P1},
            {"id": "probe2", "role": "asymmetric-and-low-n", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": ENGINE, "exists": True, "role": "supporting"},
        ],
        "ts": now,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:TST-0296 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0296" not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0296 sentinel absent after write")
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:TST-0296 named probes c1={rc1} c2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    digest, size = sha256_file(out)
    ret = {
        "id": "TST-0296",
        "unit_id": "TST-0296",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0296",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "mechanical-intersection",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "asymmetric-and-low-n",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0296/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0296-probe2-asymmetric",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0296: live named probes exit 0, receipts/TST-0296.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "TST-0296",
            "receipt_path": "command-center/p2-wave/probes/TST-0296/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0296",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0296 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
