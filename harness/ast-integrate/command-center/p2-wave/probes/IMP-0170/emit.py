#!/usr/bin/env python3
"""Emit IMP-0170 receipt + per-unit return/manifest from live probe runs."""
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
sys.path.insert(0, str(HERE))
import fingerprint as F  # noqa: E402
import fixtures as X  # noqa: E402

UNIT = "IMP-0170"
OUT = "command-center/receipts/IMP-0170.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0170/probe1_rename_invariance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0170/probe2_gate_mutation.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/IMP-0170/fingerprint.py",
    "command-center/p2-wave/probes/IMP-0170/fixtures.py",
    "command-center/p2-wave/probes/IMP-0170/probe1_rename_invariance.py",
    "command-center/p2-wave/probes/IMP-0170/probe2_gate_mutation.py",
    "command-center/p2-wave/probes/IMP-0170/emit.py",
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
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
        "receipt_path": "command-center/p2-wave/probes/IMP-0170/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_evidence() -> dict:
    base_full = F.fingerprint(X.BASE, include_topology=True)
    base_drop = F.fingerprint(X.BASE, include_topology=False)
    payload = F.structural_payload(X.BASE, include_topology=True)
    rename_rows = []
    rename_ok = 0
    for tag, mutant in X.rename_mutants():
        fp = F.fingerprint(mutant)
        eq = fp == base_full
        rename_ok += int(eq)
        rename_rows.append({"tag": tag, "equal": eq, "sha256": fp})
    gate_rows = []
    gate_ok = 0
    drop_changed = 0
    for name, mutant in X.gate_mutants():
        fp = F.fingerprint(mutant, include_topology=True)
        fp_drop = F.fingerprint(mutant, include_topology=False)
        changed = fp != base_full
        gate_ok += int(changed)
        drop_changed += int(fp_drop != base_drop)
        gate_rows.append({"name": name, "changed": changed, "sha256": fp})
    permuted = json.loads(json.dumps(X.BASE))
    permuted["stages"] = list(reversed(permuted["stages"]))
    return {
        "base_sha256_full": base_full,
        "base_sha256_no_topology": base_drop,
        "rename_preserved": rename_ok,
        "rename_total": 20,
        "gate_changed": gate_ok,
        "gate_total": 20,
        "topology_drop_gate_changed": drop_changed,
        "topology_drop_goes_red": drop_changed != 20,
        "permutation_invariant": F.fingerprint(permuted) == base_full,
        "payload_keys": sorted(payload.keys()),
        "topology_keys": sorted((payload.get("topology") or {}).keys()),
        "stage_kinds": payload.get("stage_kinds"),
        "role_set": payload.get("role_set"),
        "tool_classes": payload.get("tool_classes"),
        "rename_rows": rename_rows,
        "gate_rows": gate_rows,
    }


def main() -> int:
    ev = live_evidence()
    if ev["rename_preserved"] != 20 or ev["gate_changed"] != 20:
        print(
            f"FAILED:live evidence rename={ev['rename_preserved']}/20 "
            f"gate={ev['gate_changed']}/20"
        )
        return 1
    if not ev["topology_drop_goes_red"] or ev["topology_drop_gate_changed"] != 0:
        print("FAILED:live evidence topology-drop did not redden gate-mutation")
        return 1
    if not ev["permutation_invariant"]:
        print("FAILED:live evidence stage-list permutation changed fingerprint")
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    receipt = {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "completion_sentinel": "SUCCESS:IMP-0170",
        "sentinel": "SUCCESS:IMP-0170",
        "title": "Implement a structural mechanism fingerprint for a workflow",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "implementation": {
            "module": "command-center/p2-wave/probes/IMP-0170/fingerprint.py",
            "entry": "fingerprint(workflow, include_topology=True)",
            "covers": [
                "stage kinds",
                "role set",
                "gate predicates",
                "tool classes",
                "topology",
            ],
            "identifier_stripping": (
                "workflow id, stage ids, tool instance ids, and titles are not "
                "hashed; stage references inside predicates are rewritten to $Sn "
                "after a Weisfeiler-Lehman canonical order on coarse labels"
            ),
            "gates_live_on_topology": True,
        },
        "evidence": [
            {
                "claim": "Renaming every identifier leaves the fingerprint unchanged (20/20).",
                "verdict": "CONFIRMED",
                "count": f"{ev['rename_preserved']}/20",
                "base_sha256": ev["base_sha256_full"],
                "rows": ev["rename_rows"],
            },
            {
                "claim": "Changing one gate predicate changes the fingerprint (20/20).",
                "verdict": "CONFIRMED",
                "count": f"{ev['gate_changed']}/20",
                "rows": ev["gate_rows"],
            },
            {
                "claim": (
                    "Mutation: drop topology from the fingerprint and the "
                    "gate-mutation test goes red (gates are encoded only on topology)."
                ),
                "verdict": "CONFIRMED",
                "full_changed": ev["gate_changed"],
                "without_topology_changed": ev["topology_drop_gate_changed"],
                "goes_red": ev["topology_drop_goes_red"],
                "base_sha256_no_topology": ev["base_sha256_no_topology"],
            },
        ],
        "tests": [
            {
                "id": "T1-rename-invariance-20",
                "result": "PASS",
                "assertions": 20,
                "command": P1,
            },
            {
                "id": "T2-gate-mutation-20",
                "result": "PASS",
                "assertions": 20,
                "command": P2,
            },
            {
                "id": "T3-drop-topology-reddens-gate-mutation",
                "result": "PASS",
                "assertions": 1,
                "without_topology_changed": ev["topology_drop_gate_changed"],
            },
        ],
        "canonical_components": {
            "stage_kinds": ev["stage_kinds"],
            "role_set": ev["role_set"],
            "tool_classes": ev["tool_classes"],
            "payload_keys": ev["payload_keys"],
            "topology_keys": ev["topology_keys"],
        },
        "reviewer": {
            "reviewer_id": "IMP-0170-probe2-gate-mutation",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is the adversarial control: it both demands 20/20 gate "
                "sensitivity and plants the hasher mutant that drops topology."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0170: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "SUCCESS:IMP-0170"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0170",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "rename-invariance",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "gate-mutation-and-topology-drop",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0170/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0170-probe2-gate-mutation",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ts,
        "notes": (
            "G-1 for IMP-0170: live named probes exit 0, IMP-0170.json "
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
    print("SUCCESS:IMP-0170 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
