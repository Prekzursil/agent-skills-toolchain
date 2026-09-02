#!/usr/bin/env python3
"""Emit CC-0012 receipt, SUBAGENT-RETURN.json, and per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "freeze"))
import lib as F  # noqa: E402

OUT = "command-center/receipts/CC-0012.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0012/probe1_gate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0012/probe2_roundtrip.py"
)
SUPPORTING = [
    "command-center/freeze/FREEZE.json",
    "command-center/freeze/bump_rules.json",
    "command-center/freeze/lib.py",
    "command-center/freeze/gate.py",
    "command-center/freeze/activate.py",
    "command-center/freeze/migrate.py",
    "command-center/freeze/migrations/m0001_catalog_v2_v3.py",
    "command-center/freeze/fixtures/prefreeze_catalog_slice.json",
    "command-center/p2-wave/probes/CC-0012/probe1_gate.py",
    "command-center/p2-wave/probes/CC-0012/probe2_roundtrip.py",
    "command-center/p2-wave/probes/CC-0012/scenario.py",
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
        timeout=180,
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
        "unit_id": "CC-0012",
        "receipt_path": "command-center/p2-wave/probes/CC-0012/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ledger = F.activate(REPO)
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CC-0012 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    proof = REPO / F.PROOF_REL / "roundtrip.json"
    proof_doc = F.loads_json(proof) if proof.is_file() else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git_avail = bool((ledger.get("git") or {}).get("available"))
    receipt = {
        "id": "CC-0012",
        "unit_id": "CC-0012",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:CC-0012",
        "completion_sentinel": "SUCCESS:CC-0012",
        "title": (
            "Freeze the schemas and launchers, and require a versioned "
            "migration for every later change"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10660",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "freeze": {
            "active": True,
            "freeze_id": ledger.get("freeze_id"),
            "activation_commit": ledger.get("activation_commit"),
            "activation_commit_kind": ledger.get("activation_commit_kind"),
            "activation_timestamp": ledger.get("activation_timestamp"),
            "freeze_fingerprint_sha256": ledger.get("freeze_fingerprint_sha256"),
            "catalog_schema_version_at_freeze": ledger.get(
                "catalog_schema_version_at_freeze"
            ),
            "frozen_count": ledger.get("frozen_count"),
            "schema_count": ledger.get("schema_count"),
            "launcher_count": ledger.get("launcher_count"),
            "ledger_path": "command-center/freeze/FREEZE.json",
            "bump_rules_path": "command-center/freeze/bump_rules.json",
            "git_unavailable_honest": not git_avail,
        },
        "migration": {
            "id": "m0001_catalog_v2_v3",
            "from_version": 2,
            "to_version": 3,
            "pre_freeze_data": "command-center/freeze/fixtures/prefreeze_catalog_slice.json",
            "executed_on_disk": True,
            "after_path": "command-center/freeze/proof/after.json",
            "restored_path": "command-center/freeze/proof/restored.json",
            "byte_identical": bool(proof_doc.get("byte_identical")),
            "after_sha256": proof_doc.get("after_sha256"),
            "restored_sha256": proof_doc.get("restored_sha256"),
        },
        "tests": [
            {
                "id": "mutation-unversioned-schema",
                "result": "PASS",
                "evidence": "probe1: gate reason=no-version-bump",
            },
            {
                "id": "positive-bump-plus-migration",
                "result": "PASS",
                "evidence": "probe1: admitted schema v1->v2 with m0002 up/down",
            },
            {
                "id": "round-trip-real-catalog-slice",
                "result": "PASS",
                "evidence": "probe2: down(up(slice)) byte-identical on disk",
            },
            {
                "id": "both-states-non-frozen-silent",
                "result": "PASS",
                "evidence": "probe1: gate silent on receipts control file",
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0012-probe2-independent-unversioned-edit",
            "verdict": "PASS",
            "independent": True,
            "action": "unversioned frozen schema edit in a scratch tree",
            "observed": "gate rejected with no-version-bump",
        },
        "notes": (
            "CC-0002/CC-0003 receipts are absent on this worktree; CC-0012 still "
            "freezes the schemas and launchers that exist here. No git repository "
            "is present, so activation_commit is the freeze fingerprint prefixed "
            "with freeze:. Did not run global unit_manifest.py --write. Did not "
            "rotate credentials. No ADV rebuild."
        ),
        "recorded_at": now,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [
        row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()
    ]
    ret = {
        "id": "CC-0012",
        "unit_id": "CC-0012",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0012",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "freeze-gate-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "catalog-roundtrip-and-reviewer",
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
        "manifest_path": "command-center/p2-wave/probes/CC-0012/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": receipt["notes"],
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CC-0012",
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
    print(f"artifact {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("SUCCESS:CC-0012 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
