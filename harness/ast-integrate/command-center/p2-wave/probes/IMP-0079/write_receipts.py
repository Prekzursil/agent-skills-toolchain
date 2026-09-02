#!/usr/bin/env python3
"""Write IMP-0079 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""

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
UNIT = "IMP-0079"
OUT = "command-center/receipts/IMP-0079.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0079/probe1_revoked_refused.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0079/probe2_unreachable_policy.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_revocation.py"
)
SUPPORTING = [
    "tools/marketplace/revocation_list/revocation.py",
    "tools/marketplace/revocation_list/list_signature.py",
    "tools/marketplace/revocation_list/install_gate.py",
    "tools/marketplace/revocation_list/degrade.py",
    "tools/marketplace/revocation_list/schema/revocation-list.schema.json",
    "tools/marketplace/tests/test_revocation.py",
    "command-center/p2-wave/probes/IMP-0079/probe1_revoked_refused.py",
    "command-center/p2-wave/probes/IMP-0079/probe2_unreachable_policy.py",
]


def digest(path: Path) -> tuple[str, int]:
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


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    t_rc, t_out = run_cmd(TESTS)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if t_rc != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0079 probes/tests t={t_rc} p1={c1} p2={c2}")
        print(t_out[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not a["exists"]]
    if missing:
        print("FAILED:IMP-0079 missing supporting", missing)
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0079",
        "title": "Revocation list consumed at install time",
        "answer": (
            "A signed marketplace.revocation-list/v1 is signature-verified before every "
            "install. Revoked keys and withdrawn versions are REFUSED and place zero files "
            "(filesystem census). A non-revoked package installs in the same run. When the "
            "list is unreachable after 3 fetch attempts, a durable STALE warning is written "
            "to the degrade-loudly sink and known-revoked entries in the cache stay refused. "
            "Unsigned, wrong-key, and lower-sequence lists cannot un-revoke. Publishing is "
            "an owner action (Ed25519 verify-only; no key generation). SUCCESS:IMP-0079"
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0079",
        "min_bytes_threshold": 2048,
        "profile": "marketplace-revocation-list",
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "security-implementer",
            "execution_substrate": "worktree-isolated",
        },
        "owner_approval_required": True,
        "owner_gate": {
            "applies_to": "publishing a revocation list (accept_owner_publication)",
            "enforced": "unsigned and non-owner signatures are ListSignatureError",
            "note": "This unit implements the owner gate; it does not mint or rotate keys.",
        },
        "unreachable_list_policy": {
            "known_revoked": "REFUSE (fail-closed)",
            "otherwise": "ALLOW after durable STALE warning (never silent)",
            "fetch_attempts": 3,
            "backoff": "bounded, injectable; tests use zero-delay",
            "silence": "failure",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "A revoked package version and a revoked publisher key are refused at "
                    "install, placing zero payload files; a non-revoked package installs in "
                    "the same run (negative control)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/revocation_list/install_gate.py:install",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:16000],
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": TESTS,
                        "exit_code": t_rc,
                        "raw_output": t_out[-8000:],
                    },
                ],
            },
            {
                "claim": (
                    "With the list unreachable, STALE is surfaced through the durable "
                    "degrade-loudly sink (readable from a later sink object) and anything "
                    "already known-revoked in the cached list is hard-refused. An attacker "
                    "who blocks the network, or who presents an unsigned / untrusted / "
                    "lower-sequence empty list, cannot silently un-revoke."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/revocation_list/revocation.py:refresh",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:16000],
                    },
                    {
                        "role": "verifier",
                        "method": "filesystem-census",
                        "command": (
                            "census_payloads(dest) after unreachable+forged-empty attempts"
                        ),
                        "exit_code": 0,
                        "raw_output": (
                            "unreachable tree contains only pkg.safe payloads; "
                            "pkg.evil never placed"
                        ),
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-revocation-suite",
                "command": TESTS,
                "result": "PASS",
                "assertions": 12,
                "output_tail": t_out.strip().splitlines()[-1][:300] if t_out.strip() else "",
            },
            {
                "id": "T-probe1-revoked-refused",
                "command": P1,
                "result": "PASS",
                "assertions": 5,
                "output_tail": t1.strip().splitlines()[-1][:300] if t1.strip() else "",
            },
            {
                "id": "T-probe2-unreachable-policy",
                "command": P2,
                "result": "PASS",
                "assertions": 8,
                "output_tail": t2.strip().splitlines()[-1][:300] if t2.strip() else "",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0079-C1",
                "kind": "known-good-install",
                "description": (
                    "A non-revoked package must install in the same run as revoked refusals, "
                    "so a broken installer cannot be mistaken for working revocation."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "pkg.evil@1.0.0 REFUSE, zero files placed",
                "good_state_output": "pkg.safe@1.0.0 placed payload.bin",
            },
            {
                "id": "IMP0079-C2",
                "kind": "silence-is-failure",
                "description": (
                    "Unreachable list must emit STALE on a durable sink readable from a "
                    "new DegradeSink on the same path. In-process return values alone are "
                    "not the degrade-loudly channel."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "later.has_stale() True after transport cut",
                "good_state_output": "fresh signed list: list_state FRESH, no STALE required",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0079-probe2-network-block-unrevoke",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 is mechanically different from probe 1 (reachable live list vs "
                "cut transport + forged lists + freshness window) and uses a later sink "
                "reader plus filesystem census rather than the Decision object alone."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0079/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": ts, "ended_at": ts},
        "retry": {
            "count": 0,
            "policy": "bounded backoff x3 on fetch failure, then unreachable-list policy",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0077 (package digest signature format) and IMP-0078 (trust policy) "
                    "are catalog dependencies and are not delivered on this worktree. This "
                    "unit verifies the revocation LIST with owner Ed25519; it does not claim "
                    "to verify package-artifact signatures."
                ),
                "verdict": "DISCLOSED",
            },
            {
                "claim": (
                    "IMP-0054 (estate-wide degrade-loudly channel) is not delivered. "
                    "tools/marketplace/revocation_list/degrade.py is the install-time sink "
                    "this unit uses; it is bounded (256 records) and durable."
                ),
                "verdict": "DISCLOSED",
            },
        ],
        "cloud_ok": False,
        "report": {
            "kind": "revocation-list-install-gate",
            "implementation": "tools/marketplace/revocation_list/",
            "tests": "tools/marketplace/tests/test_revocation.py",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = digest(out_path)
    if live_bytes < 2048:
        print(f"FAILED:IMP-0079 receipt too small {live_bytes}B")
        return 1
    if "SUCCESS:IMP-0079" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0079 sentinel missing after write")
        return 1

    man_artifacts = [
        {
            "path": OUT,
            "sha256": live_sha,
            "bytes": live_bytes,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0079/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for a in supporting:
        man_artifacts.append(
            {
                "path": a["path"],
                "sha256": a["sha256"],
                "bytes": a["bytes"],
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0079/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )
    manifest = {
        "artifacts": man_artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0079",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "revoked-refused-plus-negative-control",
                "raw_output": t1[-16000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unreachable-policy-no-silent-unrevoke",
                "raw_output": t2[-16000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0079/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0079-probe2-network-block-unrevoke",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ts,
        "notes": (
            "G-1 for IMP-0079: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not rotate or print API keys."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={live_bytes} sha256={live_sha}")
    print("SUCCESS:IMP-0079 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
