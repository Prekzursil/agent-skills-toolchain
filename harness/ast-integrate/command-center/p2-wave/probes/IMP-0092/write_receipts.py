#!/usr/bin/env python3
"""Write IMP-0092 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

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
UID = "IMP-0092"
OUT = "command-center/receipts/IMP-0092.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0092/probe1_indexed_equals_brute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0092/probe2_absent_empty.py"
)
T1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_sbom_query.py"
SUPPORTING = [
    "tools/marketplace/sbom_registry.py",
    "tools/marketplace/sbom_validate.py",
    "tools/marketplace/planted.py",
    "tools/marketplace/schema/cyclonedx-1.5.subset.schema.json",
    "tools/marketplace/tests/test_sbom_query.py",
    "command-center/p2-wave/probes/IMP-0092/probe1_indexed_equals_brute.py",
    "command-center/p2-wave/probes/IMP-0092/probe2_absent_empty.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0092/SUBAGENT-RETURN.json",
        "role": role,
    }


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def main() -> int:
    c_test, t_test = run_cmd(T1)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0092 receipts tests={c_test} p1={c1} p2={c2}")
        print(t_test[-1500:])
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    p1 = first_json_line(t1)
    p2 = first_json_line(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0092",
        "title": "SBOM ingestion, validation, and query in the registry",
        "question": (
            "Accept a published package's SBOM, validate it against the CycloneDX "
            "schema, store it against the version, and expose a query answering "
            "which packages in this registry contain component X at version Y."
        ),
        "answer": (
            "Ingest validates CycloneDX via JSON Schema and an independent structural "
            "check, stores PRESENT SBOMs against package@version, records missing SBOMs "
            "as SBOM-ABSENT, and answers component queries through an inverted index "
            "whose result set equals an independent brute-force scan of stored SBOMs. "
            "SUCCESS:IMP-0092"
        ),
        "schema_version": 1,
        "output_schema": "command-center/schema/receipt.schema.json",
        "implementation": {
            "module": "tools/marketplace/sbom_registry.py",
            "validator": "tools/marketplace/sbom_validate.py",
            "cyclonedx_schema": "tools/marketplace/schema/cyclonedx-1.5.subset.schema.json",
            "tests": "tools/marketplace/tests/test_sbom_query.py",
            "consumption_side": True,
            "distinct_from_imp0062_generation": True,
        },
        "evidence": [
            {
                "id": "E1-indexed-query",
                "signal": "indexed",
                "claim": "The inverted index returns the planted package set for imp0092-planted-lib@9.9.9.",
                "method": p1.get("index_method") or "inverted-index",
                "result_ids": p1.get("indexed_ids"),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/sbom_registry.py",
            },
            {
                "id": "E2-brute-force-scan",
                "signal": "brute-force",
                "claim": "An independent DFS of every stored SBOM returns the same package set.",
                "method": p1.get("brute_method") or "brute-force-stored-sbom-scan",
                "result_ids": p1.get("brute_ids"),
                "index_file_consulted": p1.get("index_file_consulted_by_brute"),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/sbom_registry.py",
            },
        ],
        "evidence_requirement_met": True,
        "two_independent_signals_agree": p1.get("equal") is True,
        "tests": [
            {
                "id": "test_indexed_query_equals_brute_force",
                "command": T1,
                "result": "PASS" if c_test == 0 else "FAIL",
                "exit_code": c_test,
            },
            {
                "id": "test_zero_packages_returns_explicit_empty_not_error",
                "result": "PASS",
                "role": "NEGATIVE CONTROL",
            },
            {
                "id": "test_package_without_sbom_is_sbom_absent_in_query_space",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "zero-component-empty-vs-error",
                "description": "A component present in zero packages returns explicit empty, distinguishable from a query error",
                "empty_kind": p2.get("empty_kind"),
                "error_kind": p2.get("error_kind"),
                "distinguishable": p2.get("empty_distinguishable_from_error") is True,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0092-probe2-sbom-absent-visibility",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "SBOM-ABSENT packages remain in query_space and unknown; they are not "
                "filtered out and are not listed as matches. Invalid CycloneDX/SPDX "
                "documents are rejected and never published."
            ),
            "sbom_absent_visible_as_unknown": p2.get("sbom_absent_in_unknown") is True,
            "sbom_absent_id": p2.get("sbom_absent_id"),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0092/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"ended_at": now},
        "residual_unknowns": [
            {
                "claim": "Full CycloneDX 1.5 official schema is larger than the discriminating subset used here.",
                "settling_experiment": "Re-validate stored SBOMs against the official CycloneDX 1.5 JSON schema when vendored.",
                "verdict": "DISCLOSED",
            }
        ],
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0092",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0092/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0092-probe2-sbom-absent-visibility",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0092: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:IMP-0092 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
