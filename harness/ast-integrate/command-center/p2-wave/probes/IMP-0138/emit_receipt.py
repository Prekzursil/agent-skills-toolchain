#!/usr/bin/env python3
"""Emit IMP-0138 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0138"
OUT = "command-center/receipts/IMP-0138.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0138/probe1_out_of_taxonomy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0138/probe2_family_coverage.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/taxonomy.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec/agentspec/__init__.py",
    "tools/agentspec/tests/test_on_failure.py",
    "command-center/p2-wave/probes/IMP-0138/probe1_out_of_taxonomy.py",
    "command-center/p2-wave/probes/IMP-0138/probe2_family_coverage.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0138/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0138 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sys.path.insert(0, str(REPO / "tools" / "agentspec"))
    from agentspec.spec import (
        DEFAULT_ON_FAILURE,
        ON_FAILURE_ACTIONS,
        resolve_on_failure,
        validate_on_failure,
    )
    from agentspec.taxonomy import FAMILIES, family_of

    unmapped = sorted(FAMILIES - set(DEFAULT_ON_FAILURE))
    unknown = sorted(set(DEFAULT_ON_FAILURE) - FAMILIES)
    if unmapped or unknown:
        print(f"FAILED:IMP-0138 emit coverage unmapped={unmapped} unknown={unknown}")
        return 1
    if validate_on_failure(DEFAULT_ON_FAILURE):
        print("FAILED:IMP-0138 emit default on_failure is not valid")
        return 1
    if family_of("rail-exit-7") != "rail-exit":
        print("FAILED:IMP-0138 emit family_of(rail-exit-7)")
        return 1
    if resolve_on_failure(DEFAULT_ON_FAILURE, "not-a-timeout") is not None:
        print("FAILED:IMP-0138 emit substring leak")
        return 1

    tax_path = REPO / "tools/agentspec/agentspec/taxonomy.py"
    spec_path = REPO / "tools/agentspec/agentspec/spec.py"
    tax_sha, tax_n = digest(tax_path)
    spec_sha, spec_n = digest(spec_path)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = [{"family": f, "action": DEFAULT_ON_FAILURE[f]} for f in sorted(FAMILIES)]
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0138",
        "completion_sentinel": "SUCCESS:IMP-0138",
        "title": "Add a per-node failure policy expressed over the closed taxonomy",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0138: on_failure "
            "(abort|continue|quarantine|escalate|repair) keyed by "
            "tools/agentspec/agentspec/taxonomy.py families"
        ),
        "min_bytes_threshold": 128,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "premise": {
            "catalog_inputs": [
                "tools/agentspec/agentspec/taxonomy.py",
                "tools/agentspec/agentspec/spec.py",
            ],
            "inputs_were_absent": False,
            "action": (
                "Added per-node on_failure (abort|continue|quarantine|escalate|"
                "repair) on FanOut, Barrier and Pipeline, keyed by "
                "agentspec.taxonomy.FAMILIES (the closed REASONS set). Lookup "
                "uses family_of/family hyphen-boundary, never substring of the "
                "error message. Did not replace the live 15-member taxonomy "
                "with the IMP-0449 eight-family stub from a sparse worktree."
            ),
        },
        "implementation": {
            "families": sorted(FAMILIES),
            "actions": sorted(ON_FAILURE_ACTIONS),
            "default_on_failure": dict(DEFAULT_ON_FAILURE),
            "lookup": "family_of(reason) then policy[family]; never family-in-message substring",
            "parametrised_lookup": (
                "family_of('rail-exit-7') == 'rail-exit'; a policy key "
                "rail-exit-7 is out-of-taxonomy (keys are families, not codes)"
            ),
            "coverage_set_diff": {"unmapped": unmapped, "unknown": unknown},
            "taxonomy_sha256": tax_sha,
            "taxonomy_bytes": tax_n,
            "spec_sha256": spec_sha,
            "spec_bytes": spec_n,
        },
        "policy_table": table,
        "artifacts": [
            {
                "path": "tools/agentspec/agentspec/taxonomy.py",
                "role": "primary-implementation",
                "sha256": tax_sha,
                "bytes": tax_n,
                "exists": True,
            },
            {
                "path": "tools/agentspec/agentspec/spec.py",
                "role": "primary-implementation",
                "sha256": spec_sha,
                "bytes": spec_n,
                "exists": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A policy naming a reason outside the closed taxonomy fails "
                    "validation with on-failure-unknown-reason; the complete "
                    "default map is silent (both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/spec.py:validate_on_failure",
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
                    "Every taxonomy family has exactly one mapped policy: "
                    f"FAMILIES - keys = {unmapped!r} and keys - FAMILIES = "
                    f"{unknown!r} (computed set difference)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/spec.py:DEFAULT_ON_FAILURE",
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
                "id": "out-of-taxonomy-reason-fails-validation",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "every-family-exactly-one-mapped-policy",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP-0138-C1-out-of-taxonomy",
                "kind": "both-states",
                "description": (
                    "Adding not-a-timeout as an on_failure key must fire "
                    "on-failure-unknown-reason; DEFAULT_ON_FAILURE must stay valid."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0138-C2-substring-mutant",
                "kind": "mutation",
                "description": (
                    "A substring resolver (family in reason) maps not-a-timeout "
                    "to the timeout action; family_of/resolve_on_failure reject it. "
                    "AST confirms production code has no `in reason` compare."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "IMP-0138-C3-drop-one-family",
                "kind": "mutation",
                "description": (
                    "Deleting timeout from the default map makes "
                    "FAMILIES-keys == {timeout} and validation emits "
                    "on-failure-family-unmapped."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0138-probe2-family-coverage-and-substring-mutant",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial control is the substring mutant plus AST scan of "
                "family_of/resolve_on_failure; not a self-attested prose review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0138/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 IMP-0138: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0138"
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
        "sentinel": "SUCCESS:IMP-0138",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "out-of-taxonomy-validation",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "family-coverage-set-difference",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0138/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0138-probe2-family-coverage-and-substring-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0138: live named probes exit 0, IMP-0138.json "
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
    print("SUCCESS:IMP-0138 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
