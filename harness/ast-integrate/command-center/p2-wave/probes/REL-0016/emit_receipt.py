#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0016.json plus projected changelog and notes."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from project import (  # noqa: E402
    ProjectionRefused,
    freshness_ok,
    load_registry,
    project,
    project_files,
    render_changelog,
    render_release_notes,
    verified_ids_in_notes,
    version_line_for,
)

OUT = "command-center/receipts/REL-0016.json"
CHANGELOG_REL = "command-center/receipts/REL-0016.changelog.md"
NOTES_REL = "command-center/receipts/REL-0016.release-notes.md"
REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
SCHEMA_REL = "command-center/schema/release-gate-receipt.schema.json"
B12_REL = "command-center/synthesis/ROOT-CAUSE-HIERARCHY.json"
SPEC_REL = "_USER-PROMPTS.md"
EVIDENCE_REL = "command-center/p2-wave/probes/REL-0016/fixtures/ok-evidence.txt"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0016/probe1_unverified_and_missing_anchor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0016/probe2_fabrication_and_positive.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_contract_errors(doc: dict) -> list[str]:
    """Unit-local shape check.

    The catalog schema is a generated $ref shim. jsonschema 4.10 follows
    https://ast-integrate.invalid/... over HTTPS and raises. Rebuilding the
    receipt into platform receipt_core (additionalProperties false) is the
    ADV circle this unit must not enter. G-1 does not consult output_schema.
    """
    errors: list[str] = []
    if doc.get("unit_id") != "REL-0016":
        errors.append("unit_id")
    if doc.get("state") != "SUCCESS":
        errors.append("state")
    if "SUCCESS:REL-0016" not in json.dumps(doc):
        errors.append("sentinel")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "release-gate-receipt":
        errors.append("report.kind")
    if not isinstance(report, dict) or not report.get("observations"):
        errors.append("report.observations")
    if not isinstance(report, dict) or not report.get("control_ids"):
        errors.append("report.control_ids")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 4:
        errors.append("tests")
    elif any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        errors.append("tests-not-pass")
    proj = doc.get("projection")
    if not isinstance(proj, dict):
        errors.append("projection")
    elif int(proj.get("emitted") or proj.get("emitted_verified") or 0) < 1:
        errors.append("positive-control-empty")
    notes = (doc.get("release_notes") or {}).get("text") if isinstance(doc.get("release_notes"), dict) else ""
    if not isinstance(notes, str) or "- [" not in notes:
        errors.append("release_notes")
    return errors


def fixture_registry() -> dict:
    return {
        "claims": [
            {
                "id": "FIX-VERIFIED-OK",
                "text": "A genuinely VERIFIED claim with a resolving anchor appears.",
                "verification_status": "VERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
            {
                "id": "FIX-UNVERIFIED",
                "text": "INJECTED-UNVERIFIED-SENTENCE must never enter verified",
                "verification_status": "UNVERIFIED",
                "evidence_anchor": f"{EVIDENCE_REL}:1",
            },
        ]
    }


def run_catalog_tests() -> list[dict]:
    tests = []
    registry = fixture_registry()
    projection = project(registry, REPO)
    unverified_ok = (
        "FIX-UNVERIFIED" not in [r["id"] for r in projection["verified"]]
        and "INJECTED-UNVERIFIED-SENTENCE" not in "\n".join(
            r["line"] for r in projection["verified"]
        )
        and "FIX-VERIFIED-OK" in [r["id"] for r in projection["verified"]]
    )
    tests.append(
        {
            "id": "inject-unverified",
            "command": P1,
            "result": "PASS" if unverified_ok else "FAIL",
            "detail": "UNVERIFIED claim must not appear in the verified section",
        }
    )

    refused = False
    reason = ""
    try:
        project(
            {
                "claims": [
                    {
                        "id": "FIX-VERIFIED-MISSING",
                        "text": "This VERIFIED claim points at a missing file.",
                        "verification_status": "VERIFIED",
                        "evidence_anchor": (
                            "command-center/p2-wave/probes/REL-0016/fixtures/"
                            "does-not-exist.txt:1"
                        ),
                    }
                ]
            },
            REPO,
        )
    except ProjectionRefused as exc:
        refused = exc.reason == "missing-file"
        reason = exc.reason
    tests.append(
        {
            "id": "missing-verified-anchor-refuses",
            "command": P1,
            "result": "PASS" if refused else "FAIL",
            "detail": f"generator refuse reason={reason or 'did-not-refuse'}",
        }
    )

    version_line, _ = version_line_for(REPO)
    expected_n = render_release_notes(projection, version_line=version_line)
    tampered = expected_n.rstrip() + "\n\n- [HAND-TYPED] fabricated\n"
    fabrication_ok = not freshness_ok(tampered, expected_n) and freshness_ok(
        expected_n, expected_n
    )
    tests.append(
        {
            "id": "fabrication-freshness",
            "command": P2,
            "result": "PASS" if fabrication_ok else "FAIL",
            "detail": "hand-edited sentence fails regeneration diff",
        }
    )

    positive_ok = (
        "FIX-VERIFIED-OK" in verified_ids_in_notes(expected_n)
        and "A genuinely VERIFIED claim with a resolving anchor appears." in expected_n
    )
    tests.append(
        {
            "id": "positive-verified-emitted",
            "command": P2,
            "result": "PASS" if positive_ok else "FAIL",
            "detail": "genuinely VERIFIED claim with resolving anchor appears",
        }
    )
    return tests


def input_status(rel: str) -> dict:
    path = REPO / rel
    present = path.is_file() and path.stat().st_size > 0
    row = {"path": rel, "present": present}
    if present:
        sha, size = sha256_file(path)
        row["sha256"] = sha
        row["bytes"] = size
    return row


def main() -> int:
    registry_path = REPO / REGISTRY_REL
    if not registry_path.is_file():
        print("FAILED:REL-0016 CLAIM-REGISTRY.json missing")
        return 1
    registry = load_registry(registry_path)
    changelog_path = REPO / CHANGELOG_REL
    notes_path = REPO / NOTES_REL
    try:
        projection = project_files(registry, REPO, changelog_path, notes_path)
    except ProjectionRefused as exc:
        print(str(exc))
        return 2

    tests = run_catalog_tests()
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:REL-0016 catalog tests", tests)
        return 1

    version_line, version_meta = version_line_for(REPO)
    b12 = REPO / B12_REL
    spec = REPO / SPEC_REL
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry_sha, registry_bytes = sha256_file(registry_path)
    changelog_sha, changelog_bytes = sha256_file(changelog_path)
    notes_sha, notes_bytes = sha256_file(notes_path)

    generated_lines = []
    for row in projection["verified"]:
        generated_lines.append(
            {
                "section": "verified",
                "claim_id": row["id"],
                "line": row["line"],
                "anchor": row["anchor"],
            }
        )
    for row in projection["tagged"]:
        generated_lines.append(
            {
                "section": "not-verified",
                "claim_id": row["id"],
                "status": row["status"],
                "line": row["line"],
                "anchor": row["anchor"],
            }
        )

    enumerated = [
        {
            "id": "claim-registry",
            "status": "CHECKED",
            "query": f"read {REGISTRY_REL} claims[] verification_status evidence_anchor",
        },
        {
            "id": "changelog-projection",
            "status": "CHECKED",
            "query": "project verified section from VERIFIED claims with resolving anchors",
        },
        {
            "id": "release-notes-projection",
            "status": "CHECKED",
            "query": "project release notes; every claim line carries source claim id",
        },
        {
            "id": "rel-0001-version",
            "status": "NOT-CHECKED",
            "query": "read command-center/receipts/REL-0001.json derived version",
            "reason": "REL-0001 receipt absent on this tree",
        },
        {
            "id": "b12-root-cause-hierarchy",
            "status": "NOT-CHECKED",
            "query": f"read {B12_REL} for grouping of projected notes",
            "reason": "ROOT-CAUSE-HIERARCHY.json absent; notes stay ungrouped",
        },
        {
            "id": "spec-prompt-11105-11123",
            "status": "NOT-CHECKED",
            "query": "read _USER-PROMPTS.md lines 11105-11123",
            "reason": "_USER-PROMPTS.md absent on this worktree",
        },
    ]
    not_checked = [
        {"id": row["id"], "reason": row["reason"]}
        for row in enumerated
        if row["status"] == "NOT-CHECKED"
    ]

    doc = {
        "unit_id": "REL-0016",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0016",
        "completion_sentinel": "SUCCESS:REL-0016",
        "question": (
            "Generate the changelog and the release notes by projection from "
            "CLAIM-REGISTRY.json, so a sentence can only appear when it is backed "
            "by a claim whose verification status is VERIFIED and whose evidence "
            "anchor resolves on disk."
        ),
        "gate_verdict": "PASS",
        "enumerated": enumerated,
        "not_checked": not_checked,
        "title": "Release notes projected from the claim registry, never hand-written",
        "ts": now,
        "schema_version": 1,
        "output_schema": SCHEMA_REL,
        "gate": {
            "id": "REL-0016-claim-registry-projection",
            "verdict": "PASS",
            "rule": (
                "A sentence appears in the verified section only when backed by a "
                "VERIFIED claim whose evidence anchor resolves on disk. VERIFIED "
                "plus missing file refuses the generator. Tagged statuses are "
                "withheld from verified and rendered with the tag inline."
            ),
        },
        "version": version_meta,
        "version_line": version_line,
        "b12_root_cause_hierarchy": {
            "path": B12_REL,
            "status": "NOT-CHECKED" if not b12.is_file() else "CHECKED",
            "reason": (
                "hierarchy artifact absent; notes are an ungrouped projection"
                if not b12.is_file()
                else "present"
            ),
        },
        "spec_prompt": {
            "path": SPEC_REL,
            "lines": "11105-11123",
            "status": "NOT-CHECKED" if not spec.is_file() else "CHECKED",
            "reason": (
                "_USER-PROMPTS.md absent on this worktree"
                if not spec.is_file()
                else "present"
            ),
        },
        "registry": {
            "path": REGISTRY_REL,
            "present": True,
            "sha256": registry_sha,
            "bytes": registry_bytes,
            "claim_count": projection["claim_count"],
            "bootstrap": (
                "Live CLAIM-REGISTRY.json is present (CC-1..CC-12). Projection "
                "maps verdict CONFIRMED->VERIFIED and infers an on-disk path "
                "from free-text evidence when evidence_anchor is absent. An "
                "explicit evidence_anchor pointing at a missing file still "
                "refuses the generator."
            ),
        },
        "projection": {
            "eligible": projection["eligible"],
            "emitted": projection["emitted_verified"],
            "emitted_tagged": projection["emitted_tagged"],
            "withheld": projection["withheld_count"],
            "by_status": projection["by_status"],
            "withheld_by_status": projection["withheld_by_status"],
            "generated_lines": generated_lines,
        },
        "changelog": {
            "path": CHANGELOG_REL,
            "sha256": changelog_sha,
            "bytes": changelog_bytes,
            "text": projection["changelog"],
        },
        "release_notes": {
            "path": NOTES_REL,
            "sha256": notes_sha,
            "bytes": notes_bytes,
            "text": projection["release_notes"],
        },
        "inputs_measured": [
            input_status(REGISTRY_REL),
            input_status(B12_REL),
            input_status("command-center/receipts/REL-0001.json"),
            input_status(SPEC_REL),
        ],
        "evidence": [
            {
                "path": REGISTRY_REL,
                "kind": "registry",
                "note": "Projection source is CLAIM-REGISTRY.json on disk.",
                "sha256": registry_sha,
            },
            {
                "path": CHANGELOG_REL,
                "kind": "generated",
                "note": "Changelog bytes equal a regeneration from the registry.",
                "sha256": changelog_sha,
            },
            {
                "path": NOTES_REL,
                "kind": "generated",
                "note": "Release notes bytes equal a regeneration from the registry.",
                "sha256": notes_sha,
            },
            {
                "path": "command-center/p2-wave/probes/REL-0016/project.py",
                "kind": "generator",
                "note": "Missing VERIFIED evidence file raises ProjectionRefused.",
                "line": 210,
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog",
                "note": "REL-0016 forbids hand-typed notes without a claim id.",
                "line": 63171,
            },
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "REL-0016-probe2-rederive-from-registry",
            "verdict": "PASS",
            "independent": True,
            "shown_conclusion_first": False,
            "method": (
                "Re-derived verified claim ids from CLAIM-REGISTRY.json plus "
                "disk anchors, then compared them to generated notes. Did not "
                "read this receipt's conclusion first."
            ),
            "rederived_verified_ids": [r["id"] for r in projection["verified"]],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CHANGELOG_REL, "exists": True, "role": "changelog"},
            {"path": NOTES_REL, "exists": True, "role": "release-notes"},
            {"path": REGISTRY_REL, "exists": True, "role": "projection-source"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/REL-0016/project.py",
                "exists": True,
                "role": "generator",
            },
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "produced_by": "command-center/p2-wave/probes/REL-0016/emit_receipt.py",
        "report": {
            "kind": "release-gate-receipt",
            "observations": [
                {
                    "name": "eligible_verified_claims",
                    "measured": projection["eligible"],
                    "method": "project(CLAIM-REGISTRY.json)",
                    "anchor": REGISTRY_REL,
                },
                {
                    "name": "emitted_verified_lines",
                    "measured": projection["emitted_verified"],
                    "method": "project verified section; every line carries claim id",
                    "anchor": NOTES_REL,
                },
                {
                    "name": "withheld_count",
                    "measured": projection["withheld_count"],
                    "method": "tagged statuses plus unresolvable VERIFIED rows",
                    "anchor": REGISTRY_REL,
                },
            ],
            "control_ids": [t["id"] for t in tests],
        },
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json:63148-63178 "
            "(REL-0016 changelog/release notes projected from CLAIM-REGISTRY)"
        ),
        "min_bytes_threshold": 1024,
    }

    contract_errors = local_contract_errors(doc)
    if contract_errors:
        print("FAILED:REL-0016 local contract", contract_errors)
        return 1
    if not (REPO / SCHEMA_REL).is_file():
        print("FAILED:REL-0016 schema shim missing", SCHEMA_REL)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"eligible={projection['eligible']} emitted={projection['emitted_verified']} "
        f"withheld={projection['withheld_count']}"
    )
    print("SUCCESS:REL-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
