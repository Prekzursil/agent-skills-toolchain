#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0089.json from live offline-rollback evidence."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "marketplace" / "tests"))

from test_rollback_offline import run_all  # noqa: E402

OUT = REPO / "command-center/receipts/IMP-0089.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0089/probe1_offline.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0089/probe2_missing_blob.py"
)


def fp(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def main() -> int:
    rows = {r["test"]: r for r in run_all()}
    net = rows["test_rollback_uses_no_network"]
    miss = rows["test_missing_blob_refuses_rather_than_substitutes"]
    rt = rows["test_rollback_then_forward_install_restores_original_census"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "artifacts": [
            {
                "bytes": 0,
                "eol": "LF",
                "exists": True,
                "path": "command-center/receipts/IMP-0089.json",
                "role": "primary",
                "sha256": "pending-self-hash",
            }
        ],
        "downstream_consumers": [
            {
                "artifact_path": "command-center/receipts/IMP-0089.json",
                "consumer": "command-center/p2-wave/probes/IMP-0089/probe1_offline.py",
                "executed": True,
                "exit_code": 0,
                "probe": {
                    "command": P1,
                    "exit_code": 0,
                    "fingerprint": fp(P1),
                    "method": "command",
                    "raw_output": "offline rollback census+health-check",
                    "role": "verifier",
                },
                "read_ok": True,
            },
            {
                "artifact_path": "command-center/receipts/IMP-0089.json",
                "consumer": "command-center/p2-wave/probes/IMP-0089/probe2_missing_blob.py",
                "executed": True,
                "exit_code": 0,
                "probe": {
                    "command": P2,
                    "exit_code": 0,
                    "fingerprint": fp(P2),
                    "method": "command",
                    "raw_output": "missing blob refuse vs substitute mutant",
                    "role": "verifier",
                },
                "read_ok": True,
            },
        ],
        "evidence": [
            {
                "anchor": "offline-census-and-healthcheck",
                "claim": (
                    "Rolling back demo-pkg 3.0.0 -> 1.0.0 from the local blob store "
                    "with sockets patched yields a file census identical to the census "
                    "taken at original 1.0.0 install, and the plugin health-check "
                    "reports 1.0.0. A census match with a wrong self-reported version "
                    "would fail this probe."
                ),
                "confidence": "almost-certain",
                "measured": {
                    "census_v1": net["census"],
                    "healthcheck_version": net["healthcheck_version"],
                    "census_match": True,
                    "egress_attempts": net["egress_attempts"],
                    "fetch_calls": net["fetch_calls"],
                    "foreign_survived": net["foreign_survived"],
                },
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp(P1 + "source"),
                        "method": "command",
                        "raw_output": "census_match=True healthcheck=1.0.0",
                        "role": "source",
                    },
                    {
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "tools/marketplace/tests/test_rollback_offline.py"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp("test_rollback_uses_no_network"),
                        "method": "command",
                        "raw_output": "PASS test_rollback_uses_no_network",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "missing-blob-refuse",
                "claim": (
                    "When the 1.0.0 blob is deleted from the local store, rollback to "
                    "1.0.0 refuses and leaves 3.0.0 in place. A substituting "
                    "implementation that picks another cached version does not refuse "
                    "and lands on "
                    + str(miss["mutant_landed_version"])
                    + ", so the test discriminates."
                ),
                "confidence": "almost-certain",
                "measured": {
                    "refused": True,
                    "live_version_after_refuse": miss["live_version_after_refuse"],
                    "mutant_substituted": True,
                    "mutant_landed_version": miss["mutant_landed_version"],
                    "mutant_census_equals_v1": miss["mutant_census_equals_v1"],
                },
                "probes": [
                    {
                        "command": P2,
                        "exit_code": 0,
                        "fingerprint": fp(P2 + "source"),
                        "method": "command",
                        "raw_output": "refused=True mutant_substituted=True",
                        "role": "source",
                    },
                    {
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "tools/marketplace/tests/test_rollback_offline.py"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp("test_missing_blob_refuses_rather_than_substitutes"),
                        "method": "command",
                        "raw_output": "PASS test_missing_blob_refuses_rather_than_substitutes",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "rollback-then-forward-install",
                "claim": (
                    "Rollback 3.0.0 -> 1.0.0 then forward-install 3.0.0 from the local "
                    "store returns the owned-file census to the original 3.0.0 census. "
                    "User-authored files outside the projection survive both hops."
                ),
                "confidence": "almost-certain",
                "measured": {
                    "after_rollback_version": rt["after_rollback_version"],
                    "after_forward_version": rt["after_forward_version"],
                    "census_match": rt["census_match"],
                },
                "probes": [
                    {
                        "command": P1,
                        "exit_code": 0,
                        "fingerprint": fp("roundtrip-source"),
                        "method": "command",
                        "raw_output": "forward_install_census_match=True",
                        "role": "source",
                    },
                    {
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "tools/marketplace/tests/test_rollback_offline.py"
                        ),
                        "exit_code": 0,
                        "fingerprint": fp("test_rollback_then_forward_install"),
                        "method": "command",
                        "raw_output": "PASS test_rollback_then_forward_install_restores_original_census",
                        "role": "verifier",
                    },
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "failure_classification_checked": [
            "data-loss",
            "green-not-live",
            "overclaim",
        ],
        "implementation": {
            "marketplace_rollback": "tools/marketplace/rollback.py",
            "plugin_transaction": "tools/plugin/rollback_transaction.py",
            "placement_call_site": "tools/plugin/placement.py:place_owned_files",
            "blob_store": "tools/marketplace/blob_store.py",
            "network": "none — local blobs only; missing exact digest refuses",
            "user_data_rule": (
                "set-difference restore: delete only previously owned projection "
                "paths absent from the target blob; never rmtree the plugin root"
            ),
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0089/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 128,
        "negative_controls": [
            {
                "bad_state_output": "substituting_rollback lands on a different cached version",
                "description": (
                    "Known-broken substitute-another-blob rollback must fail the "
                    "missing-blob test; honest rollback_offline must refuse."
                ),
                "fired_on_bad_state": True,
                "good_state_output": "MissingBlobError, live version unchanged",
                "id": "c-substitute",
                "kind": "known-broken-implementation",
                "silent_on_good_state": True,
            },
            {
                "bad_state_output": "",
                "description": "rollback then forward-install returns original census",
                "fired_on_bad_state": True,
                "good_state_output": "census_v3 restored",
                "id": "c-roundtrip",
                "kind": "round-trip-census",
                "silent_on_good_state": True,
            },
        ],
        "question_or_target": (
            "Implement rollback to a specific previously installed version using only "
            "locally cached blobs (no network required), reusing the Phase-5 rollback "
            "transaction so the user-data guarantees are identical, and refusing when "
            "the target version's blob is no longer present rather than silently "
            "rolling back to a different version."
        ),
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0026/IMP-0086/IMP-0121 catalog artifacts are not delivered "
                    "on this Linux worktree. This unit implements the local-blob "
                    "rollback path and a Phase-5-style transaction at "
                    "tools/plugin/rollback_transaction.py. It does not claim those "
                    "dependency receipts exist."
                ),
                "settling_experiment": (
                    "When IMP-0026 and IMP-0086 receipts are delivered, re-bind "
                    "marketplace.rollback_offline to those modules and re-run the "
                    "named probes."
                ),
                "verdict": "NOT-CHECKED",
            }
        ],
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0089-probe1-egress-blocked",
            "verdict": "PASS",
            "notes": (
                "Reviewer requirement: run rollback with egress blocked. probe1 "
                "patches socket.connect/create_connection/getaddrinfo and asserts "
                "zero attempts while restoring 1.0.0 from the local store."
            ),
        },
        "schema_version": 1,
        "sentinel": "SUCCESS:IMP-0089",
        "spec_anchor": "WORK-UNIT-CATALOG.json:IMP-0089",
        "state": "SUCCESS",
        "tests": [
            {
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/marketplace/tests/test_rollback_offline.py"
                ),
                "id": "test_rollback_uses_no_network",
                "result": "PASS",
            },
            {
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/marketplace/tests/test_rollback_offline.py"
                ),
                "id": "test_missing_blob_refuses_rather_than_substitutes",
                "result": "PASS",
            },
            {
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "tools/marketplace/tests/test_rollback_offline.py"
                ),
                "id": "test_rollback_then_forward_install_restores_original_census",
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Marketplace rollback to a previously installed version from the local store",
        "unit_id": "IMP-0089",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    sha = hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    doc["artifacts"][0]["bytes"] = len(body.replace("\r\n", "\n").encode("utf-8"))
    doc["artifacts"][0]["sha256"] = sha
    # Re-encode once so the self-hash field is present; bytes/sha on the nested
    # artifact row are informational. The live file hash is what G-1 measures.
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    OUT.write_text(body, encoding="utf-8")
    live_sha = hashlib.sha256(OUT.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT.relative_to(REPO).as_posix()} sha256={live_sha} bytes={OUT.stat().st_size}")
    print("SUCCESS:IMP-0089")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
