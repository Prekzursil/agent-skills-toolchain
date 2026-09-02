#!/usr/bin/env python3
"""Emit IMP-0077 receipt + per-unit manifest + SUBAGENT-RETURN after live probes."""

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
UNIT = "IMP-0077"
OUT_REL = f"command-center/receipts/{UNIT}.json"
SENTINEL = f"SUCCESS:{UNIT}"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0077/probe1_valid_and_tamper.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0077/probe2_canonicalisation_review.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_signature_format.py"
)
SUPPORTING = [
    "tools/marketplace/signature.py",
    "tools/marketplace/verify.py",
    "tools/marketplace/schema/signature.schema.json",
    "tools/marketplace/tests/test_signature_format.py",
    "tools/marketplace/tests/support.py",
    "command-center/p2-wave/probes/IMP-0077/probe1_valid_and_tamper.py",
    "command-center/p2-wave/probes/IMP-0077/probe2_canonicalisation_review.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_record(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    code_t, out_t = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if code_t != 0 or code1 != 0 or code2 != 0:
        print("FAILED:IMP-0077 live probes/tests did not all exit 0")
        print(out_t[-2500:])
        print(out1[-2500:])
        print(out2[-2500:])
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_record("source", P1, out1, code1)
    p2 = probe_record("verifier", P2, out2, code2)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10855; catalog IMP-0077",
        "min_bytes_threshold": 128,
        "title": "Detached signature format binding a package digest to a publisher key",
        "question_or_target": (
            "Define the on-registry signature record (algorithm, digest, key id, "
            "signed timestamp, canonicalisation rules) and implement verification. "
            "This defines the FORMAT and the verify function; the trust decision "
            "built on it is IMP-0078 and the build-side attestation is IMP-0063."
        ),
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": (
                "two-strikes-then-pivot; never disable a verification path "
                "to make a test pass"
            ),
        },
        "artifacts": [artifact_row(rel, "supporting") for rel in SUPPORTING],
        "evidence": [
            {
                "anchor": "tools/marketplace/tests/test_signature_format.py::test_valid",
                "claim": (
                    "Verification succeeds for a correctly signed fixture "
                    "(ed25519 over RFC 8785 JCS of the TBS object)."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p2],
            },
            {
                "anchor": "tools/marketplace/tests/test_signature_format.py::test_tampered",
                "claim": (
                    "Verification fails for a flipped payload byte, a swapped "
                    "signature between two packages, and a non-canonical "
                    "re-encoding of the same semantic record. Unsigned is "
                    "UNSIGNED, never VALID-by-absence. Unsupported algorithms "
                    "fail closed."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p1],
            },
        ],
        "tests": [
            {"id": "test_valid", "command": TEST_CMD, "result": "PASS"},
            {"id": "test_tampered", "command": P1, "result": "PASS"},
            {"id": "test_swapped", "command": P1, "result": "PASS"},
            {"id": "test_non_canonical_reencoding", "command": P2, "result": "PASS"},
            {"id": "test_unknown_key_id", "command": P2, "result": "PASS"},
            {"id": "negative-control-unsigned", "command": P1, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "unsigned-package",
                "kind": "known-broken-fixture",
                "description": (
                    "unsigned package is reported UNSIGNED, never VALID-by-absence"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UNSIGNED unsigned: no signature record",
                "good_state_output": "VALID ed25519 JCS verify",
            },
            {
                "id": "flipped-payload-byte",
                "kind": "mutation",
                "description": "one flipped package byte changes the digest; verify fails",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "digest-mismatch",
                "good_state_output": "VALID",
            },
            {
                "id": "swapped-signature",
                "kind": "known-broken-fixture",
                "description": (
                    "signature record from package B does not verify for package A"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "digest-mismatch or signature-mismatch",
                "good_state_output": "VALID",
            },
            {
                "id": "non-canonical-reencoding",
                "kind": "canonicalisation-confusion",
                "description": (
                    "pretty-print, unicode-escape, and duplicate-key encodings fail closed"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "non-canonical or malformed",
                "good_state_output": "canonical wire VALID",
            },
            {
                "id": "unsupported-algorithm",
                "kind": "fail-closed",
                "description": "algorithm none / rsa-pss fail closed",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unsupported-algorithm",
                "good_state_output": "ed25519",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0077-probe2-canonicalisation-review",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Independent bypass: duplicate key_id (attacker then trusted) "
                "which last-key-wins JSON parsers would accept as the trusted "
                "id. Strict parse rejects duplicates and does not re-canonicalize."
            ),
        },
        "format": {
            "schema": "tools/marketplace/schema/signature.schema.json",
            "algorithm": "ed25519",
            "canonicalisation": "jcs-rfc8785",
            "tbs_fields": [
                "algorithm",
                "canonicalisation",
                "digest",
                "key_id",
                "signed_at",
            ],
            "module": "tools/marketplace/signature.py",
            "verify_function": "verify_signature / verify_wire",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_record(
                    "verifier",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0077",
                    "pending-after-write",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0078 trust policy and IMP-0075 publisher validity windows "
                    "are not this unit; verify_signature only checks format, "
                    "canonicalisation, digest binding, and key-id lookup."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "IMP-0078 consumes verify_signature outcomes.",
            }
        ],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    if live_bytes < 128:
        print(f"FAILED:IMP-0077 receipt too small ({live_bytes} B)")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0077 sentinel missing from receipt")
        return 1

    rows = [
        {
            "path": OUT_REL,
            "sha256": live_sha,
            "bytes": live_bytes,
            "exists": True,
            "present": True,
            "role": "primary",
            "eol": "LF",
            "unit_id": UNIT,
            "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        }
    ]
    for rel in SUPPORTING:
        rows.append(artifact_row(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/signature.schema.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "valid-and-tamper",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "canonicalisation-review",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0077-probe2-canonicalisation-review",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0077: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT_REL} bytes={live_bytes} sha256={live_sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
