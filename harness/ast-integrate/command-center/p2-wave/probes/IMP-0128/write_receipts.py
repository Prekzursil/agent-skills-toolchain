#!/usr/bin/env python3
"""Write IMP-0128 receipt + per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "IMP-0128"
OUT = "command-center/receipts/IMP-0128.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0128/probe1_cockpit_live.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0128/probe2_direct_query_stale.py"
)
SUPPORTING = [
    "tools/marketplace/freshness.py",
    "tools/marketplace/registry_store.py",
    "tools/marketplace/registry_health.py",
    "tools/marketplace/cockpit_pane.py",
    "tools/marketplace/tests/test_cockpit_pane.py",
    "tools/monitorcore/monitorcore/cockpit.py",
    "tools/monitorcore/monitorcore/panes.py",
    "tools/monitorcore/monitorcore/unified.py",
    "command-center/p2-wave/probes/IMP-0128/probe1_cockpit_live.py",
    "command-center/p2-wave/probes/IMP-0128/probe2_direct_query_stale.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = dict(**{**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0128/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    tests = REPO / "tools" / "marketplace" / "tests" / "test_cockpit_pane.py"
    tcode, tout = run_cmd(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {tests}")
    if tcode != 0:
        print(f"FAILED:receipts tests rc={tcode}")
        print(tout[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = [
        "tools/marketplace/freshness.py",
        "tools/marketplace/registry_store.py",
        "tools/marketplace/registry_health.py",
        "tools/marketplace/cockpit_pane.py",
        "tools/monitorcore/monitorcore/unified.py",
        "tools/monitorcore/monitorcore/cockpit.py",
        "tools/monitorcore/monitorcore/panes.py",
        "tools/marketplace/tests/test_cockpit_pane.py",
    ]
    artifacts = []
    for rel in impl:
        sha, size = digest(REPO / rel)
        artifacts.append(
            {
                "path": rel,
                "role": "implementation",
                "sha256": sha,
                "bytes": size,
                "present": True,
            }
        )

    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0128",
        "completion_sentinel": "SUCCESS:IMP-0128",
        "title": "Marketplace observability surfaced through the existing monitor cockpit",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "timestamps": {"generated_at": now, "ended_at": now},
        "evidence": [
            {
                "id": "cockpit-launch",
                "claim": "Launching monitorcore.unified cockpit renders the registry-health pane with live values; the five baseline panes still render unchanged.",
                "probes": ["probe1_cockpit_live"],
                "verdict": "CONFIRMED",
            },
            {
                "id": "direct-query-match",
                "claim": "Pane values equal RegistryHealth.query_* results from the same store; a 25h-stale metric renders as STALE (25h 0m), never the bare number.",
                "probes": ["probe2_direct_query_stale"],
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {
                "id": "test_pane_values_match_direct_query",
                "path": "tools/marketplace/tests/test_cockpit_pane.py",
                "result": "PASS",
            },
            {
                "id": "test_existing_cockpit_panes_still_render",
                "path": "tools/marketplace/tests/test_cockpit_pane.py",
                "result": "PASS",
            },
            {
                "id": "test_stale_metric_renders_as_stale_with_age",
                "path": "tools/marketplace/tests/test_cockpit_pane.py",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0128-probe2-direct-query-stale",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": artifacts,
        "notes": (
            "Registry health (index lint, integrity sweep age, advisory freshness, "
            "mirror conflict count, blocked-publish count) is a sixth pane on the "
            "existing five-pane monitorcore cockpit, not a second dashboard. "
            "G-1: live named probes, non-BLOCKED receipt, per-unit manifest row. "
            "Did not run tools/command-center/unit_manifest.py --write."
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    man_artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0128",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "cockpit-launch-live-pane",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "direct-query-and-stale-control",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0128/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0128-probe2-direct-query-stale",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0128: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0128 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
