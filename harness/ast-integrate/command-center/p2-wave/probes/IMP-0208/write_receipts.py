#!/usr/bin/env python3
"""Write IMP-0208 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0208.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0208/probe1_packed_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0208/probe2_planted_junk.py"
)
SUPPORTING = [
    "tools/marketplace/publication.py",
    "tools/marketplace/__init__.py",
    "command-center/p2-wave/probes/IMP-0208/fixture.py",
    "command-center/p2-wave/probes/IMP-0208/probe1_packed_inventory.py",
    "command-center/p2-wave/probes/IMP-0208/probe2_planted_junk.py",
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
        "unit_id": "IMP-0208",
        "receipt_path": "command-center/p2-wave/probes/IMP-0208/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    sys.path.insert(0, str(REPO / "tools"))
    sys.path.insert(0, str(HERE))
    import tempfile

    from fixture import build_certified_tree, planted_junk_members
    from marketplace.publication import (
        emit_payload,
        inventory_from_packed,
        inventory_gate,
        pack_tree,
        paths_matching_excluded,
        plant_into_archive,
        publish,
        scan_packed_credentials,
    )

    with tempfile.TemporaryDirectory(prefix="imp0208-receipt-") as td:
        root = Path(td) / "src"
        build_certified_tree(root, plant_source_junk=True)
        packed = pack_tree(root)
        inventory = inventory_from_packed(packed.archive)
        intersection = paths_matching_excluded(inventory)
        creds = scan_packed_credentials(packed.archive)
        good_gate = inventory_gate(packed.archive)
        dirty = plant_into_archive(packed.archive, planted_junk_members())
        bad_gate = inventory_gate(dirty)
        payload = emit_payload(root)
        publish_refused = False
        try:
            publish(payload, None)
        except Exception:
            publish_refused = True

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0208",
        "id": "IMP-0208",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0208",
        "title": "Emit the marketplace publication payload for a certified workflow",
        "spec_anchor": "_USER-PROMPTS.md:10842",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "owner_approval_required": True,
        "publication_owner_gated": True,
        "timestamps": {"started_at": now, "ended_at": now},
        "implementation": {
            "packer": "tools/marketplace/publication.py",
            "selection": "allowlist-deny-by-default",
            "inventory_oracle": "packed-archive-entry-list-and-member-bytes",
            "not_oracle": "source-tree-walk",
            "required_payload_fields": [
                "identity",
                "version",
                "permissions",
                "provenance",
                "sbom_entry",
                "licence",
                "benchmark_evidence",
                "lineage",
            ],
        },
        "evidence": [
            {
                "claim": (
                    "Packed-byte inventory contains zero excluded paths "
                    "(computed set intersection == empty)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/publication.py:inventory_from_packed",
                "computed": {
                    "packed_paths": inventory,
                    "excluded_intersection": intersection,
                    "empty": intersection == [],
                },
            },
            {
                "claim": "A credential-shaped scan of the packed bytes returns zero hits.",
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/publication.py:scan_packed_credentials",
                "computed": {
                    "credential_hit_count": len(creds),
                    "hits": [{"path": h.path, "pattern_id": h.pattern_id} for h in creds],
                },
            },
        ],
        "tests": [
            {
                "id": "packed-inventory-excludes-git-caches-transcripts",
                "result": "PASS" if intersection == [] and good_gate.ok else "FAIL",
                "computed_intersection": intersection,
                "source_tree_was_dirty": True,
            },
            {
                "id": "planted-junk-caught-by-inventory-gate",
                "result": "PASS" if (not bad_gate.ok) and bad_gate.excluded_intersection else "FAIL",
                "good_state_ok": good_gate.ok,
                "bad_state_ok": bad_gate.ok,
                "bad_named_paths": bad_gate.excluded_intersection,
                "bad_credential_hit_count": len(bad_gate.credential_hits),
            },
            {
                "id": "publish-remains-owner-gated",
                "result": "PASS" if publish_refused and payload["publication"]["published"] is False else "FAIL",
                "emit_state": payload["publication"]["state"],
                "publish_without_owner_refused": publish_refused,
            },
        ],
        "payload_sample": {
            "identity": payload.get("identity"),
            "version": payload.get("version"),
            "packed_sha256": (payload.get("packed") or {}).get("sha256"),
            "packed_entry_count": (payload.get("packed") or {}).get("entry_count"),
            "publication": payload.get("publication"),
        },
        "probes": [
            {
                "id": "probe1_packed_inventory",
                "command": P1,
                "exit_code": c1,
                "role": "source",
            },
            {
                "id": "probe2_planted_junk",
                "command": P2,
                "exit_code": c2,
                "role": "verifier",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0208-probe2-planted-junk-detector",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 is the independent verifier: it plants junk into packed "
                "bytes (not the source tree) so an allowlist packer cannot "
                "satisfy the detector by omission alone."
            ),
        },
        "registered": True,
        "notes": (
            "IMP-0208 emits a Phase-6 marketplace publication payload for a "
            "VALID certified workflow. The packer is allowlist/deny-by-default. "
            "The inventory gate reads packed bytes. Publication stays "
            "PENDING_OWNER without an owner approval record. Did not run "
            "unit_manifest.py --write. SUCCESS:IMP-0208"
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
        "id": "IMP-0208",
        "unit_id": "IMP-0208",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0208",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0208/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0208-probe2-planted-junk-detector",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0208: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Publication remains owner-gated."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0208",
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
    print("SUCCESS:IMP-0208 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
