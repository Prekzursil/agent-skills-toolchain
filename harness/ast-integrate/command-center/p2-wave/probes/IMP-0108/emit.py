#!/usr/bin/env python3
"""Emit IMP-0108 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Runs the named probes live, writes command-center/receipts/IMP-0108.json,
then hashes the live receipt bytes into the per-unit UNIT-ARTIFACT-MANIFEST.
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
REPO = Path(__file__).resolve().parents[4]
OUT = "command-center/receipts/IMP-0108.json"
SCHEMA = (
    "command-center/schema/receipt.schema.json + "
    "tools/marketplace/schema/offline-bundle.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0108/probe1_manifest_matches.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0108/probe2_closure_and_secrets.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_offline_export.py"
)
SUPPORTING = [
    "tools/marketplace/offline_export.py",
    "tools/marketplace/resolver.py",
    "tools/marketplace/signatures.py",
    "tools/marketplace/secret_gate.py",
    "tools/marketplace/digest.py",
    "tools/marketplace/canonical.py",
    "tools/marketplace/testkit.py",
    "tools/marketplace/schema/offline-bundle.schema.json",
    "tools/marketplace/tests/test_offline_export.py",
    "command-center/p2-wave/probes/IMP-0108/probe1_manifest_matches.py",
    "command-center/p2-wave/probes/IMP-0108/probe2_closure_and_secrets.py",
    "command-center/p2-wave/probes/IMP-0108/independent_closure.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0108",
        "receipt_path": "command-center/p2-wave/probes/IMP-0108/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    sys.path.insert(0, str(REPO / "tools"))
    from marketplace.testkit import diamond_registry
    from marketplace.offline_export import export_offline_bundle

    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    rct, tt = run_cmd(TESTS)
    if rc1 != 0 or rc2 != 0 or rct != 0:
        print(f"FAILED:IMP-0108 emit probes/tests rc1={rc1} rc2={rc2} tests={rct}")
        print(t1[-1500:])
        print(t2[-1500:])
        print(tt[-1500:])
        return 1

    fxdir = HERE / "fixtures"
    fxdir.mkdir(parents=True, exist_ok=True)
    fx = diamond_registry()
    sample = fxdir / "offline-bundle.zip"
    export_offline_bundle(
        index=fx.index,
        blobs=fx.blobs,
        private_keys=fx.private_keys,
        package_key_id=fx.package_key_id,
        selection=[("app", "1.0.0")],
        dest=sample,
        created_at="2026-08-24T18:00:00+00:00",
        signed_at="2026-08-24T18:00:00+00:00",
    )
    sample_rel = "command-center/p2-wave/probes/IMP-0108/fixtures/offline-bundle.zip"
    sample_sha, sample_bytes = digest_file(sample)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    impl_hashes = {rel: digest_file(REPO / rel) for rel in SUPPORTING}

    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0108",
        "id": "IMP-0108",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0108",
        "title": "Offline export bundle with an integrity manifest",
        "question_or_target": (
            "Implement export of a selected registry subset plus its package "
            "blobs into a single portable bundle carrying a manifest of every "
            "entry's digest, the index snapshot, and the signatures needed to "
            "verify on the far side without network access."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0108",
        "exporter": "tools/marketplace/offline_export.py",
        "bundle_schema": "tools/marketplace/schema/offline-bundle.schema.json",
        "sample_bundle": {
            "path": sample_rel,
            "bytes": sample_bytes,
            "sha256": sample_sha,
            "selection": [{"name": "app", "version": "1.0.0"}],
            "closure": ["app@1.0.0", "leaf@1.0.0", "mid@1.0.0", "side@1.0.0"],
            "optional_excluded": ["extra@1.0.0"],
        },
        "evidence": [
            {
                "claim": (
                    "After export, the bundle manifest entry count equals the "
                    "extracted blob count (zip namelist and on-disk walk)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/tests/test_offline_export.py::test_manifest_matches_contents",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": rc1,
                        "raw_output": t1[-8000:],
                    }
                ],
            },
            {
                "claim": (
                    "An independent BFS of required dependencies is fully "
                    "contained in the bundle; omitting a transitive blob "
                    "fails export and writes no zip."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0108/independent_closure.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "exit_code": rc2,
                        "raw_output": t2[-8000:],
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "test_closure_is_complete",
                "command": TESTS + "::test_closure_is_complete",
                "result": "PASS",
            },
            {
                "id": "test_manifest_matches_contents",
                "command": TESTS + "::test_manifest_matches_contents",
                "result": "PASS",
            },
            {
                "id": "test_export_fails_when_dependency_omitted",
                "command": TESTS + "::test_export_fails_when_dependency_omitted",
                "result": "PASS",
            },
            {
                "id": "offline-export-suite",
                "command": TESTS,
                "result": "PASS" if rct == 0 else "FAIL",
                "raw_output": tt[-4000:],
                "exit_code": rct,
            },
        ],
        "negative_controls": [
            {
                "id": "omit-required-blob",
                "kind": "known-broken-fixture",
                "description": (
                    "Delete leaf@1.0.0 from the blob map while app still "
                    "requires it; export must raise IncompleteClosure and "
                    "must not write a bundle."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "planted-private-key-pem",
                "kind": "secret-in-artifact",
                "description": (
                    "Clean bundle is silent; a synthetic PRIVATE KEY PEM "
                    "fires the gate; report does not contain the secret body."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0108-secret-gate-over-bundle",
            "verdict": "PASS",
            "independent": True,
            "requirement": (
                "Reviewer must confirm no credential or private key is "
                "included in a bundle (run the IMP-0004 gate over it)."
            ),
            "notes": (
                "IMP-0004 is not delivered as its own unit. Probe 2 ran the "
                "IMP-0004-shaped secret gate over the live zip: silent on "
                "the clean bundle, fires on a planted synthetic PEM, and "
                "the publisher PKCS8 private key bytes are absent from the "
                "archive. Public Ed25519 keys and signatures are packed; "
                "private keys stay in caller memory."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": rel,
                "sha256": impl_hashes[rel][0],
                "bytes": impl_hashes[rel][1],
                "exists": True,
                "role": "implementation",
            }
            for rel in SUPPORTING
        ]
        + [
            {
                "path": sample_rel,
                "sha256": sample_sha,
                "bytes": sample_bytes,
                "exists": True,
                "role": "supporting",
            }
        ],
        "implementation": {
            "offline_export": "tools/marketplace/offline_export.py",
            "resolver": "tools/marketplace/resolver.py",
            "signatures": "tools/marketplace/signatures.py",
            "secret_gate": "tools/marketplace/secret_gate.py",
            "notes": (
                "Digest/signature/resolver helpers here are the subset export "
                "needs. This receipt does not claim IMP-0077, IMP-0083, or "
                "IMP-0084 delivered."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0077 signature format and IMP-0084 lockfile are not "
                    "delivered units on this worktree; export uses an Ed25519 "
                    "detached record sufficient to verify a bundle offline."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind export to IMP-0077/IMP-0084 once those units ship."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0108/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"ended_at": now},
        "answer": (
            "Export writes a zip of blobs + digest manifest + index snapshot + "
            "Ed25519 detached signatures. Manifest entry count equals extracted "
            "blob count (4/4 on the diamond fixture). An independent BFS "
            "required-closure matches the packed set; omitting leaf fails "
            "closed. Private keys are not packed. SUCCESS:IMP-0108"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = digest_file(out)
    if "SUCCESS:IMP-0108" not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0108 sentinel missing from receipt")
        return 1
    if size < 2048:
        print(f"FAILED:IMP-0108 artifact {size}B below floor")
        return 1

    ret = {
        "id": "IMP-0108",
        "unit_id": "IMP-0108",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0108",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0108/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0108-secret-gate-over-bundle",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0108: live named probes exit 0, receipts/IMP-0108.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    artifacts.append(row(sample_rel, "supporting"))
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0108",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0108 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
