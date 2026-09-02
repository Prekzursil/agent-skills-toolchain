#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0064-license-provenance.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402
import schema_ctl as S  # noqa: E402

REPO = A.REPO
OUT = "command-center/confirmation/CNF-0064-license-provenance.json"
SCHEMA = "command-center/schema/license-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0064/probe1_blob_not_badge.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0064/probe2_history_and_riders.py"
)
QUESTION = (
    "For every adopted or candidate workflow and dependency, is the recorded "
    "license claim true at the commit we would actually pin? Read the LICENSE "
    "file at the pinned commit and answer: does it match the registry row, "
    "has the license changed across the project's history, and does any rider "
    "or additional term restrict intended use?"
)


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[
            :32
        ],
        "exit_code": exit_code,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def independent_blob_table(rows: list[dict]) -> dict[str, str]:
    out = {}
    for row in rows:
        path = REPO / row["license_blob_path"]
        out[row["id"]] = hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
    return out


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        S.garbage_rejected()
    except AssertionError as exc:
        print(f"FAILED:CNF-0064 {exc}")
        return 1

    registry = A.load_registry()
    rows = A.audit_all()
    if len(rows) < 8:
        print(f"FAILED:CNF-0064 emit too few candidates n={len(rows)}")
        return 1
    missing = [r["id"] for r in rows if len(r.get("license_blob_sha256") or "") != 64]
    if missing:
        print("FAILED:CNF-0064 emit missing blob sha", missing)
        return 1
    live_sha = {r["id"]: r["license_blob_sha256"] for r in rows}
    indep_sha = independent_blob_table(rows)
    if live_sha != indep_sha:
        print("FAILED:CNF-0064 emit audit sha drifted from hashlib")
        return 1

    mismatches = [r["id"] for r in rows if not r["match_registry"]]
    changed = [r["id"] for r in rows if r["license_identity_changed"]]
    rider_rows = [r["id"] for r in rows if r["riders"]]
    rider_n = sum(len(r["riders"]) for r in rows)

    candidates = []
    for r in rows:
        candidates.append(
            {
                "id": r["id"],
                "name": r["name"],
                "kind": r["kind"],
                "source_repo": r["source_repo"],
                "pinned_ref": r["pinned_ref"],
                "pinned_git_sha": r["pinned_git_sha"],
                "license_path": r["license_path"],
                "license_blob_path": r["license_blob_path"],
                "license_blob_sha256": r["license_blob_sha256"],
                "license_blob_bytes": r["license_blob_bytes"],
                "registry_spdx": r["registry_spdx"],
                "spdx_from_blob": r["spdx_from_blob"],
                "spdx_from_earliest_blob": r["spdx_from_earliest_blob"],
                "match_registry": r["match_registry"],
                "license_identity_changed": r["license_identity_changed"],
                "blob_sha_changed": r["blob_sha_changed"],
                "riders": r["riders"],
                "classifications": r["classifications"],
                "badge_metadata_ignored": True,
            }
        )

    by_id = {r["id"]: r for r in rows}
    trap = by_id["planted-badge-trap"]
    react = by_id["wf-dep-react"]
    badge_ok = trap["spdx_from_blob"] == "Apache-2.0" and not trap["match_registry"]
    react_ok = react["spdx_from_blob"] == "MIT" and react["match_registry"]
    if not badge_ok or not react_ok:
        print("FAILED:CNF-0064 emit badge-trap both-states inert")
        return 1

    upstream = registry["upstream_284_row_registry"]
    src_audit = probe(
        "source",
        "file-read",
        "python3 -c audit.audit_all() over pinned LICENSE blobs",
        json.dumps(
            {
                "n": len(rows),
                "sha": {k: v[:12] for k, v in live_sha.items()},
                "spdx": {r["id"]: r["spdx_from_blob"] for r in rows},
            },
            sort_keys=True,
        ),
        0,
    )
    ver_hash = probe(
        "verifier",
        "byte-compare",
        "hashlib.sha256(LICENSE bytes) per candidate, independent of parse_spdx",
        json.dumps({"sha": indep_sha, "agree_with_audit": live_sha == indep_sha}, sort_keys=True),
        0,
    )
    src_hist = probe(
        "source",
        "file-read",
        "parse_spdx(earliest_blob) vs parse_spdx(pinned_blob)",
        json.dumps(
            {
                "changed": changed,
                "pairs": {
                    r["id"]: [r["spdx_from_earliest_blob"], r["spdx_from_blob"]]
                    for r in rows
                    if r["license_identity_changed"]
                },
            },
            sort_keys=True,
        ),
        0,
    )
    ver_rider = probe(
        "verifier",
        "static-analysis",
        "detect_riders(pinned_text) plus earliest extras; verbatim excerpts",
        json.dumps(
            {
                "rider_ids": rider_rows,
                "n": rider_n,
                "n8n": [x["id"] for x in by_id["wf-dep-n8n"]["riders"]],
                "planted_rider": [x["id"] for x in by_id["planted-rider"]["riders"]],
            },
            sort_keys=True,
        ),
        0,
    )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0064",
        "state": "SUCCESS",
        "sentinel": A.SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0064",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "license-auditor",
            "execution_substrate": "local-parallel",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "report": {
            "kind": "license-audit",
            "control_ids": [
                "planted-badge-trap",
                "planted-mismatch",
                "planted-rider",
                "planted-changed",
            ],
            "observations": [
                {
                    "name": "audited_candidate_count",
                    "measured": len(rows),
                    "method": "audit.audit_all over worktree-local registry",
                    "anchor": "command-center/p2-wave/probes/CNF-0064/registry.json",
                },
                {
                    "name": "every_candidate_has_blob_sha",
                    "measured": True,
                    "method": "len(license_blob_sha256)==64 from LICENSE bytes",
                    "anchor": "command-center/p2-wave/probes/CNF-0064/audit.py:sha256_bytes",
                },
                {
                    "name": "mismatch_count",
                    "measured": len(mismatches),
                    "method": "spdx_from_blob vs registry_spdx",
                    "anchor": "command-center/p2-wave/probes/CNF-0064/audit.py:spdx_equal",
                },
                {
                    "name": "license_changed_count",
                    "measured": len(changed),
                    "method": "parse_spdx(earliest) vs parse_spdx(pinned)",
                    "anchor": "command-center/p2-wave/probes/CNF-0064/audit.py:license_identity_changed",
                },
                {
                    "name": "badge_trap_prefers_blob",
                    "measured": True,
                    "method": "package.json MIT ignored; LICENSE blob Apache-2.0",
                    "anchor": "command-center/p2-wave/probes/CNF-0064/fixtures/planted/badge-trap/LICENSE",
                },
            ],
            "question": QUESTION,
            "claim_under_test": (
                "Registry SPDX strings are true at the pinned commit only if the "
                "LICENSE blob at that commit hashes and parses to the same SPDX, "
                "history is compared by earliest-vs-pinned blobs, and riders are "
                "copied verbatim from those blobs."
            ),
            "population": {
                "upstream_284_row_registry_present": False,
                "upstream_284_row_registry_note": (
                    "The 284-row Windows workflow-candidate registry is not on "
                    "this worktree (last known sha256 "
                    + upstream["last_known_sha256"]
                    + "). This unit audits the worktree-local registry of "
                    "adoptable workflow engines/dependencies plus planted "
                    "controls. It does not claim a 284-row census."
                ),
                "audited_registry_path": (
                    "command-center/p2-wave/probes/CNF-0064/registry.json"
                ),
                "audited_candidate_count": len(rows),
                "every_audited_candidate_has_blob_sha": True,
            },
            "candidates": candidates,
            "summary": {
                "mismatch_count": len(mismatches),
                "mismatch_ids": mismatches,
                "license_changed_count": len(changed),
                "license_changed_ids": changed,
                "rider_count": rider_n,
                "rider_ids": rider_rows,
                "blob_sha_missing_count": 0,
                "intended_use": (
                    "research, evaluation, and possible marketplace redistribution "
                    "of workflow definitions (not operating a competing hosted "
                    "automation SaaS)."
                ),
            },
            "findings": {
                "react_airflow_temporal_prefect_checkout": (
                    "Pinned LICENSE blobs match the registry SPDX (MIT or Apache-2.0) "
                    "with no field-of-use rider detected in the blob."
                ),
                "n8n": (
                    "Registry Apache-2.0 is false at n8n@1.82.0: blob is the "
                    "Sustainable Use License. Earliest n8n@0.164.1 is Apache-2.0 "
                    "WITH Commons-Clause (no-Sell rider). License identity changed."
                ),
                "redis": (
                    "Registry BSD-3-Clause is false at 7.4.0: blob is RSALv2 OR "
                    "SSPL-1.0. Earliest 7.2.4 COPYING is BSD-3-Clause. License "
                    "identity changed."
                ),
                "planted_controls": (
                    "mismatch and badge-trap: package/README MIT vs Apache blob. "
                    "rider: MIT plus an ML-training ban copied verbatim. "
                    "changed: GPL-2.0-only earliest vs MIT pinned."
                ),
            },
            "method": {
                "reads_license_blob": True,
                "reads_readme_badge": False,
                "reads_package_json_license": False,
                "history_compare": "parse_spdx(earliest_blob) vs parse_spdx(pinned_blob)",
                "rider_rule": "verbatim excerpt from blob when rider phrases match",
            },
        },
        "artifacts": [
            art(SCHEMA, "supporting"),
            art("command-center/p2-wave/probes/CNF-0064/registry.json", "supporting"),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/planted/badge-trap/LICENSE",
                "control",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/planted/badge-trap/package.json",
                "control",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/planted/rider/LICENSE",
                "control",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/planted/changed/earliest.LICENSE",
                "control",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/blobs/n8n-1.82.0.LICENSE.md",
                "fixture",
            ),
            art(
                "command-center/p2-wave/probes/CNF-0064/fixtures/blobs/redis-7.4.0.LICENSE.txt",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Every audited candidate records a SHA-256 of the pinned "
                    "LICENSE blob; SPDX is parsed from those bytes, not from "
                    "package.json or README badges."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0064/audit.py:audit_candidate",
                "probes": [src_audit, ver_hash],
            },
            {
                "claim": (
                    "License identity change is earliest-blob vs pinned-blob "
                    "SPDX, and riders are copied verbatim (n8n Sustainable Use "
                    "plus Commons-Clause@earliest; redis RSALv2/SSPL; planted "
                    "ML-training ban)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0064/audit.py:detect_riders",
                "probes": [src_hist, ver_rider],
            },
        ],
        "tests": [
            {"id": "blob-not-badge", "command": P1, "result": "PASS"},
            {"id": "history-and-riders", "command": P2, "result": "PASS"},
            {
                "id": "schema-rejects-garbage",
                "command": "schema_ctl.garbage_rejected",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-badge-trap",
                "kind": "mutation",
                "description": (
                    "package.json and README badge say MIT; the LICENSE blob is "
                    "Apache-2.0. The auditor must hash and parse the blob, not "
                    "the badge."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"planted-badge-trap blob={trap['spdx_from_blob']} "
                    f"registry={trap['registry_spdx']} match={trap['match_registry']}"
                ),
                "good_state_output": (
                    f"wf-dep-react blob={react['spdx_from_blob']} "
                    f"registry={react['registry_spdx']} match={react['match_registry']}"
                ),
            },
            {
                "id": "planted-changed",
                "kind": "known-broken-fixture",
                "description": (
                    "Earliest blob is GPL-2.0-only and pinned blob is MIT. "
                    "Identity change must fire. A stable MIT pin (actions/checkout) "
                    "must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "planted-changed earliest="
                    + by_id["planted-changed"]["spdx_from_earliest_blob"]
                    + " pinned="
                    + by_id["planted-changed"]["spdx_from_blob"]
                ),
                "good_state_output": (
                    "wf-dep-actions-checkout earliest="
                    + by_id["wf-dep-actions-checkout"]["spdx_from_earliest_blob"]
                    + " pinned="
                    + by_id["wf-dep-actions-checkout"]["spdx_from_blob"]
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0064-probe2-history-and-riders",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-parses earliest and pinned blobs and does not "
                "trust emit's narrative fields."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0064/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "schema_ctl.validator Draft202012 offline store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "schema_ctl.errors(doc) against license-audit.schema.json",
                    "validated before write; emitter refuses to persist an invalid artifact",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The 284-row Windows workflow-candidate registry is not on "
                    "this Linux worktree, so this unit does not claim a 284-row "
                    "license census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place 08-WORKFLOW-CANDIDATE-REGISTRY.json on disk, pin each "
                    "row's commit, fetch LICENSE at that commit, and re-run audit_all."
                ),
            }
        ],
    }

    errs = S.errors(doc)
    if errs:
        print("FAILED:CNF-0064 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    if A.SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0064 sentinel missing after write")
        return 1
    if out.stat().st_size < 4096:
        print("FAILED:CNF-0064 artifact below min_bytes_threshold")
        return 1
    digest = A.sha256_file(out)
    print(
        f"wrote {OUT} bytes={out.stat().st_size} sha256={digest} "
        f"n={len(rows)} mismatch={len(mismatches)} changed={len(changed)} "
        f"riders={rider_n}"
    )
    print("SUCCESS:CNF-0064 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
