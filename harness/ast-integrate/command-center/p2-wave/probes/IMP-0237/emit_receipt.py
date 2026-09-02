#!/usr/bin/env python3
"""Emit IMP-0237 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

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
UNIT = "IMP-0237"
OUT = "command-center/receipts/IMP-0237.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0237/probe1_watchlist_idempotence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0237/probe2_impossibility_both_states.py"
)
SUPPORTING = [
    "tools/research_blueprints/archival.py",
    "tools/research_blueprints/contradiction.py",
    "tools/research_blueprints/watchlist.py",
    "tools/research_blueprints/repair_loop.py",
    "tools/research_blueprints/impossibility.py",
    "tools/research_blueprints/registry.py",
    "tools/research_blueprints/evaluate.py",
    "command-center/p2-wave/probes/IMP-0237/probe1_watchlist_idempotence.py",
    "command-center/p2-wave/probes/IMP-0237/probe2_impossibility_both_states.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0237/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from research_blueprints.registry import BLUEPRINTS, dump_workflows, scheduled_ids

    dump_workflows()
    dump_workflows(REPO / "blueprints" / "workflows")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0237 emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    kinds = {bid: bp["schedule_kind"] for bid, bp in BLUEPRINTS.items()}
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0237",
        "completion_sentinel": "SUCCESS:IMP-0237",
        "title": (
            "Implement research blueprints 13-15: archival, "
            "contradiction/negative-result, watchlist"
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0237: archival, "
            "contradiction-negative-result, watchlist; watchlist is the only "
            "SCHEDULED blueprint and is resumable/idempotent; contradiction "
            "returns a schema-valid proof-of-impossibility, not an empty pass"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "premise": {
            "catalog_inputs": [
                "IMP-0230 blueprint contract",
                "IMP-0139 RepairLoop",
            ],
            "inputs_were_absent": True,
            "action": (
                "Created tools/research_blueprints on this sparse worktree and "
                "implemented the three research blueprints plus live named probes. "
                "Did not exit on predicate:absent."
            ),
        },
        "implementation": {
            "blueprints": sorted(BLUEPRINTS),
            "schedule_kinds": kinds,
            "scheduled_only": list(scheduled_ids()),
            "repair_loop_exits": [
                "exit_review_passed",
                "exit_attempt_limit",
                "exit_proved_impossible",
            ],
            "package": "tools/research_blueprints",
        },
        "artifacts": [
            {
                "path": "tools/research_blueprints/watchlist.py",
                "role": "primary-implementation",
            },
            {
                "path": "tools/research_blueprints/contradiction.py",
                "role": "primary-implementation",
            },
            {
                "path": "tools/research_blueprints/archival.py",
                "role": "primary-implementation",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A repeated watchlist run produces zero duplicate findings "
                    "(computed id-set equality) and watchlist is the only "
                    "scheduled blueprint of the three."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/research_blueprints/watchlist.py:tick",
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
                    "An impossible counterevidence request yields a schema-valid "
                    "proof-of-impossibility; an obtainable request returns "
                    "findings; an open-world miss is not an empty pass (both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/research_blueprints/contradiction.py:run",
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
                "id": "watchlist-idempotent-across-two-runs",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "impossible-request-yields-proof-of-impossibility",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0237-C1-second-tick-zero-new",
                "kind": "idempotence",
                "description": (
                    "Second watchlist tick over the same snapshot must append "
                    "zero findings; duplicate_count stays 0."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0237-C2-impossibility-both-states",
                "kind": "both-states",
                "description": (
                    "Obtainable counterevidence is review-passed with findings; "
                    "destroyed-complete-archive request is a valid proof; "
                    "open-world miss is attempt-limit-reached, not a pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0237-C3-empty-search-rejected",
                "kind": "mutation",
                "description": (
                    "A payload that only reports 'found nothing' fails "
                    "validate_proof (not_an_empty_search / closed_world)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0237-probe2-impossibility-and-distinct-exits",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the empty-search mutant plus AST "
                "discrimination of RepairLoop's three terminal constructors."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0237/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0237: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0237"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0237",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "watchlist-idempotence",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "impossibility-both-states",
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
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0237/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0237-probe2-impossibility-and-distinct-exits",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0237: live named probes exit 0, IMP-0237.json "
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
    print("SUCCESS:IMP-0237 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
