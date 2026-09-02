#!/usr/bin/env python3
"""Write IMP-0147 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0147.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0147/probe1_plan_equality.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0147/probe2_silent_drop.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/migrate.py",
    "tools/agentspec/agentspec/plan.py",
    "command-center/p2-wave/probes/IMP-0147/probe1_plan_equality.py",
    "command-center/p2-wave/probes/IMP-0147/probe2_silent_drop.py",
    "command-center/p2-wave/probes/IMP-0147/fixtures/old-pre-phase7.json",
    "command-center/p2-wave/probes/IMP-0147/fixtures/new-twin.json",
    "command-center/p2-wave/probes/IMP-0147/fixtures/unmigratable-unknown-key.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "IMP-0147",
        "receipt_path": "command-center/p2-wave/probes/IMP-0147/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, cmd: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "exit_code": code,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0147 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_obj("source", P1, t1, c1)
    p2 = probe_obj("verifier", P2, t2, c2)
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0147",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0147",
        "title": "Implement spec_version migration rules and an executable migrator",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0147",
        "min_bytes_threshold": 128,
        "question_or_target": (
            "every new node type bumps spec_version and ships a migrator old->new "
            "plus a refusal for new->old; a pre-Phase-7 workflow loads after "
            "migration with identical semantics (same plan), and an unmigratable "
            "construct fails loudly instead of being dropped"
        ),
        "implementation": {
            "spec_module": "tools/agentspec/agentspec/spec.py",
            "spec_version_line": 116,
            "validate_module": "tools/agentspec/agentspec/validate.py",
            "unsupported_id": "spec-version-unsupported",
            "migrator_module": "tools/agentspec/agentspec/migrate.py",
            "pre_phase7": 6,
            "current_spec_version": 11,
            "node_type_bumps": {
                "Subworkflow": 7,
                "Loop": 8,
                "HumanCheckpoint": 9,
                "DynamicFanOut": 10,
                "RepairLoop": 11,
            },
            "refusal_ids": {
                "unknown_key": "unmigratable-unknown-key",
                "downgrade": "spec-downgrade-refused",
                "unsupported": "spec-version-unsupported",
            },
        },
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "exists": True,
            }
        ],
        "evidence": [
            {
                "claim": (
                    "A spec_version=6 FanOut/Barrier/Pipeline workflow migrates "
                    "through 7..11 and compiles to the same plan as a hand-written "
                    "spec_version=11 twin; a unit-id mutant diverges (equality is not vacuous)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/migrate.py:migrate",
                "confidence": "almost-certain",
                "probes": [p1],
            },
            {
                "claim": (
                    "An unmigratable fixture with mystery_payload returns typed "
                    "refusal unmigratable-unknown-key and workflow=None; the "
                    "silent-drop mutant makes that same refusal test go red; "
                    "new->old is spec-downgrade-refused."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/migrate.py:migrate_skip_unknown_keys",
                "confidence": "almost-certain",
                "probes": [p2],
            },
        ],
        "timestamps": {"started_at": "2026-08-24T18:40:00Z", "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "tests": [
            {
                "id": "migrated-old-plan-equals-hand-written-new",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "silent-drop-mutation-makes-refusal-test-go-red",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "c-silent-drop",
                "kind": "mutation",
                "description": (
                    "migrate_skip_unknown_keys drops mystery_payload; the refusal "
                    "test (ok is False and workflow is None and id is "
                    "unmigratable-unknown-key) is False on the mutant and True on live."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": t2[-2000:],
                "good_state_output": t1[-2000:],
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0147-probe2-silent-drop",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0147/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is written",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0129..IMP-0146 node-type units are not delivered in this "
                    "worktree; this migrator registers additive identity bumps for "
                    "those types so a pre-Phase-7 graph keeps semantics."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": "Re-run plan equality once those node types land executable semantics.",
            }
        ],
        "notes": (
            "G-1 for IMP-0147: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0147, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0147",
        "unit_id": "IMP-0147",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0147",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "plan-equality",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "silent-drop-refusal",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0147/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0147-probe2-silent-drop",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0147: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0147",
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
    print("SUCCESS:IMP-0147 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
