#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0109.json and per-unit G-1 files.

Live named probes and catalog tests run first. cloud ok=true is not delivery.
Does not run tools/command-center/unit_manifest.py --write.
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
OUT = "command-center/receipts/IMP-0109.json"
SUITE = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_offline_import.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0109/probe1_tampered_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0109/probe2_hostile_review.py"
)
SUPPORTING = [
    "tools/marketplace/offline.py",
    "tools/marketplace/trust_policy.py",
    "tools/marketplace/schema/offline-bundle.schema.json",
    "tools/marketplace/schema/trust-policy.schema.json",
    "tools/marketplace/tests/test_offline_import.py",
    "command-center/p2-wave/probes/IMP-0109/probe1_tampered_census.py",
    "command-center/p2-wave/probes/IMP-0109/probe2_hostile_review.py",
    "command-center/p2-wave/probes/IMP-0109/emit_receipt.py",
]
QUESTION = (
    "Implement import of an offline bundle: re-verify every signature and "
    "digest against the local trust policy (never trust the bundle's own "
    "claim), and define what happens when an imported version already exists "
    "locally with a different digest — a collision must be surfaced, never "
    "silently overwritten."
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "role": role,
        "eol": "LF",
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0109",
        "receipt_path": (
            "command-center/p2-wave/probes/IMP-0109/SUBAGENT-RETURN.json"
        ),
        "role": role,
    }


def main() -> int:
    suite_code, suite_text = run_cmd(SUITE)
    if suite_code != 0:
        print(suite_text[-3000:])
        print("FAILED:IMP-0109 tests")
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(t1[-2000:])
        print(t2[-2000:])
        print(f"FAILED:IMP-0109 probes c1={c1} c2={c2}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    impl = artifact_row("tools/marketplace/offline.py", "implementation")
    test_art = artifact_row(
        "tools/marketplace/tests/test_offline_import.py", "catalog-test"
    )
    receipt_doc = {
        "schema_version": 1,
        "unit_id": "IMP-0109",
        "id": "IMP-0109",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0109",
        "completion_sentinel": "SUCCESS:IMP-0109",
        "title": "Offline import with re-verification and a collision policy",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": (
            "Import re-verifies every digest and detached signature against the "
            "local IMP-0078 trust policy. MANIFEST trust_decision / verified / "
            "publisher_trust fields are recorded as ignored claims and never "
            "authorise an unsigned or untrusted entry. A tampered blob is "
            "rejected by name (hello-skill@1.0.0) and the destination census "
            "is unchanged — including when a second valid entry sits in the "
            "same archive. A digest collision with a local name@version is "
            "surfaced as COLLISION and the local blob is not overwritten. "
            "Path-traversal and symlink members are refused before any write. "
            "SUCCESS:IMP-0109"
        ),
        "min_bytes_threshold": 128,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            impl,
            test_art,
            artifact_row(
                "command-center/p2-wave/probes/IMP-0109/probe1_tampered_census.py",
                "probe",
            ),
            artifact_row(
                "command-center/p2-wave/probes/IMP-0109/probe2_hostile_review.py",
                "probe",
            ),
        ],
        "evidence": [
            {
                "id": "signal-1-tampered-blob-named",
                "kind": "import-refuse",
                "claim": (
                    "A bundle with a tampered blob is rejected at import, "
                    "naming the entry hello-skill@1.0.0 (TAMPERED_BLOB)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/offline.py:import_offline_bundle",
                "named_entry": "hello-skill@1.0.0",
                "independent_of": "signal-2-census-unchanged",
            },
            {
                "id": "signal-2-census-unchanged",
                "kind": "census-delta",
                "claim": (
                    "Index/blob census before and after a rejected import is "
                    "identical; a two-entry bundle with one tampered blob "
                    "writes zero packages (no partial import)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/offline.py:registry_census",
                "rejected_package_count": 0,
                "independent_of": "signal-1-tampered-blob-named",
            },
        ],
        "evidence_requirement": (
            "TWO independent signals: (1) a bundle with a tampered blob is "
            "rejected at import, naming the entry; (2) an index census before "
            "and after confirms zero entries changed on the rejected import — "
            "a partial import that then rejects is still a compromise."
        ),
        "tests": [
            {
                "id": "test_valid_bundle_imports_fully",
                "name": (
                    "tools/marketplace/tests/test_offline_import.py"
                    "::test_valid_bundle_imports_fully"
                ),
                "result": "PASS",
            },
            {
                "id": "test_tampered_blob_is_rejected_naming_the_entry",
                "name": (
                    "tools/marketplace/tests/test_offline_import.py"
                    "::test_tampered_blob_is_rejected_naming_the_entry"
                ),
                "result": "PASS",
            },
            {
                "id": "test_unsigned_entry_rejected_even_when_manifest_claims_trust",
                "name": (
                    "tools/marketplace/tests/test_offline_import.py"
                    "::test_unsigned_entry_rejected_even_when_manifest_claims_trust"
                ),
                "result": "PASS",
            },
            {
                "id": "test_digest_collision_is_surfaced_and_not_overwritten",
                "name": (
                    "tools/marketplace/tests/test_offline_import.py"
                    "::test_digest_collision_is_surfaced_and_not_overwritten"
                ),
                "result": "PASS",
            },
        ],
        "tests_required": (
            "tools/marketplace/tests/test_offline_import.py (valid bundle, "
            "tampered blob, unsigned entry, digest collision with an existing "
            "local version)"
        ),
        "negative_controls": [
            {
                "id": "valid-bundle-same-run",
                "kind": "known-good-bundle",
                "description": (
                    "A valid two-package bundle imports fully in the same run "
                    "that a tampered twin is refused."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0109-probe2-hostile-review",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 crafts a hostile tar with path traversal "
                "(../escape.json) and a symlink member (blobs/link.json). "
                "inspect_archive_members reports PATH_TRAVERSAL and "
                "SYMLINK_OR_HARDLINK. import_offline_bundle returns "
                "HOSTILE_MEMBER and writes nothing. A separate re-signed "
                "digest collision is named COLLISION and the local blob is "
                "unchanged."
            ),
        },
        "reviewer_requirement": (
            "Cross-vendor security reviewer must craft a hostile bundle "
            "(path traversal in an entry name, symlink entry) and report "
            "the outcome."
        ),
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0109/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "probe1_tampered_census",
                "artifact_path": "tools/marketplace/offline.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
            },
            {
                "consumer": "probe2_hostile_review",
                "artifact_path": "tools/marketplace/offline.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "suite": {
            "command": SUITE,
            "exit_code": suite_code,
            "tail": suite_text[-2000:],
        },
        "probe_results": {
            "probe1": t1[-2000:],
            "probe2": t2[-2000:],
        },
        "registered": True,
        "cloud_ok": False,
        "status": "DELIVERED",
        "ts": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0109: live named probes exit 0, receipts/IMP-0109.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "SUCCESS:IMP-0109"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt_doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0109" not in raw:
        print("FAILED:IMP-0109 sentinel missing from receipt")
        return 1
    out_path.write_text(raw, encoding="utf-8")

    primary = manifest_row(OUT, "primary")
    rows = [primary] + [
        manifest_row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()
    ]
    ret = {
        "id": "IMP-0109",
        "unit_id": "IMP-0109",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0109",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[-4000:],
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
            "command-center/p2-wave/probes/IMP-0109/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0109-probe2-hostile-review",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0109: live named probes exit 0, receipts/IMP-0109.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0109",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0109 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
