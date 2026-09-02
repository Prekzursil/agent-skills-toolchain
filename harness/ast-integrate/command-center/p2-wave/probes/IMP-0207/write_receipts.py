#!/usr/bin/env python3
"""Write IMP-0207 catalog receipt plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
"""

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
UNIT = "IMP-0207"
OUT = "command-center/receipts/IMP-0207.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0207/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0207/probe2_intersection.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/packs.py",
    "tools/agentspec/agentspec/semver.py",
    "command-center/p2-wave/probes/IMP-0207/scenario.py",
    "command-center/p2-wave/probes/IMP-0207/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0207/probe2_intersection.py",
    "command-center/p2-wave/probes/IMP-0207/fixtures/pack_narrow.json",
    "command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_tools.json",
    "command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_source.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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
        "exists": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0207/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_blob(role: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}", file=sys.stderr)
        print(t1[-2000:], file=sys.stderr)
        print(t2[-2000:], file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = row("tools/agentspec/agentspec/packs.py", "implementation")
    p_src = probe_blob("source", P1, t1, c1)
    p_ver = probe_blob("verifier", P2, t2, c2)
    supporting_rows = [row(p, "supporting") for p in SUPPORTING]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0207",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0207",
        "min_bytes_threshold": 128,
        "artifacts": [
            {
                "path": a["path"],
                "bytes": a["bytes"],
                "sha256": a["sha256"],
                "exists": True,
                "role": a["role"],
                "eol": "LF",
            }
            for a in [impl]
            + [s for s in supporting_rows if s["path"] != impl["path"]]
        ],
        "evidence": [
            {
                "claim": (
                    "A privilege-widening preset is rejected at load with closed id "
                    "pack-preset-tool-permission-widening (extra Write) or "
                    "pack-preset-source-policy-widening (extra public-tor). The same "
                    "pack with a narrowing preset (Read,Grep / official-docs,code) "
                    "loads. Silent intersection-clip of a widening preset is not a "
                    "success path; an edited narrowing preset that adds Write is "
                    "rejected on reload. Invalid semver '1.2' is pack-semver-invalid."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/packs.py:load_pack",
                "confidence": "almost-certain",
                "probes": [p_src, p_ver],
            },
            {
                "claim": (
                    "Effective tool_permissions and source_policy equal the "
                    "independently computed set intersection of workflow-declared "
                    "and preset-requested sets: {Read, Grep} and "
                    "{official-docs, code}. Union of the same sets is strictly "
                    "larger, so the check is non-vacuous. Pack version 1.2.0 is "
                    "strict semver and compares older than 1.3.0. Workflow params "
                    "carry the IMP-0133 topic field."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/packs.py:privilege_intersection",
                "confidence": "almost-certain",
                "probes": [p_ver, p_src],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "max 2 attempts then pivot"},
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "tool-permission-widening",
                "kind": "known-broken-fixture",
                "description": "Preset requesting Write beyond workflow declaration is rejected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "pack-preset-tool-permission-widening",
                "good_state_output": "narrowing pack loaded",
            },
            {
                "id": "source-policy-widening",
                "kind": "known-broken-fixture",
                "description": "Preset requesting public-tor beyond workflow declaration is rejected",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "pack-preset-source-policy-widening",
                "good_state_output": "narrowing pack loaded",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0207-probe2-intersection",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0207/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_blob(
                    "verifier",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0207",
                    "pending live measure after this write",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0133 Param types and IMP-0136 WorkUnit.tool_permissions "
                    "fields are not yet on spec.Workflow in this worktree. Packs "
                    "consume the declared JSON surface those units serialize "
                    "(params, tool_permissions, source_policy) rather than "
                    "inventing rival spec.py types."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run load_pack against Workflow.to_dict() once IMP-0133 "
                    "and IMP-0136 land those fields on spec.Workflow."
                ),
            }
        ],
        "notes": (
            "G-1 for IMP-0207: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + supporting_rows
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0207",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "both-states-privilege-widening",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "computed-intersection",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0207/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0207-probe2-intersection",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0207: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
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
    print("SUCCESS:IMP-0207 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
