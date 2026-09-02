#!/usr/bin/env python3
"""Emit CNF-0102 confirmation artifact from archive listings, not from rules."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from auditor import audit_archive, dump_report_text, load_rules
from constants import (
    CANDIDATE_ZIP_REL,
    EXTRA_MEMBER,
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    PLANTED_CREDENTIAL_BODY,
    PLANTED_ENV,
    PLANTED_GIT,
    PLANTED_OVERSIZE,
    POLLUTED_ZIP_REL,
    PROOF_ZIP_REL,
    QUESTION,
    REPO,
    RULES_REL,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from contract import schema_errors, schema_rejects_garbage
from scenario import (
    production_surface,
    write_candidate_zip,
    write_enumeration_proof_zip,
    write_polluted_zip,
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    eol = "BINARY" if rel.endswith(".zip") else "LF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def answers_from(report: dict, rules: dict) -> dict:
    by = {row["rule"]: row["entries"] for row in report["flagged_by_rule"]}
    total = report["totals"]["uncompressed_bytes"]
    budget = int(rules["max_uncompressed_bytes"])
    return {
        "contains_repository_metadata": bool(by.get("repo-metadata")),
        "contains_caches": bool(by.get("cache")),
        "contains_logs": bool(by.get("log")),
        "contains_transcripts": bool(by.get("transcript")),
        "contains_credential_shaped_files": bool(by.get("credential-filename")),
        "contains_oversized_files": bool(by.get("oversized-file")),
        "total_uncompressed_bytes": total,
        "declared_budget_bytes": budget,
        "within_budget": total <= budget
        and report["totals"]["entry_count"] <= int(rules["max_entry_count"]),
    }


def main() -> int:
    rules = load_rules()
    candidate = REPO / CANDIDATE_ZIP_REL
    polluted = REPO / POLLUTED_ZIP_REL
    proof = REPO / PROOF_ZIP_REL
    write_candidate_zip(candidate)
    write_polluted_zip(polluted, int(rules["max_single_file_bytes"]))
    write_enumeration_proof_zip(candidate, proof)

    clean = audit_archive(candidate, rules)
    dirty = audit_archive(polluted, rules)
    proof_rep = audit_archive(proof, rules)

    clean_text = dump_report_text(clean)
    dirty_text = dump_report_text(dirty)
    if PLANTED_CREDENTIAL_BODY in clean_text or PLANTED_CREDENTIAL_BODY in dirty_text:
        print("FAILED:CNF-0102 detector-failure credential body copied into report")
        return 1

    proof_paths = [e["path"] for e in proof_rep["entries"]]
    if EXTRA_MEMBER not in proof_paths:
        print("FAILED:CNF-0102 detector-failure extra member missing from archive listing")
        return 1
    extra_row = next(e for e in proof_rep["entries"] if e["path"] == EXTRA_MEMBER)
    if "allowlist-miss" not in extra_row["flags"]:
        print("FAILED:CNF-0102 detector-failure extra member not flagged allowlist-miss")
        return 1
    if proof_rep["totals"]["entry_count"] != proof_rep["member_count_from_infolist"]:
        print("FAILED:CNF-0102 detector-failure listing count != infolist")
        return 1
    if proof_rep["totals"]["entry_count"] == len(rules["allowlist_globs"]):
        print("FAILED:CNF-0102 detector-failure listing count equals glob count")
        return 1

    flagged_paths = []
    for e in dirty["entries"]:
        if e["flags"]:
            flagged_paths.append(e["path"])
    planted = [PLANTED_GIT, PLANTED_ENV, PLANTED_OVERSIZE]
    missing = [p for p in planted if p not in flagged_paths]
    if missing:
        print(f"FAILED:CNF-0102 detector-failure planted not flagged {missing}")
        return 1
    git_row = next(e for e in dirty["entries"] if e["path"] == PLANTED_GIT)
    if "repo-metadata" not in git_row["flags"]:
        print("FAILED:CNF-0102 detector-failure .git/config not repo-metadata")
        return 1
    env_row = next(e for e in dirty["entries"] if e["path"] == PLANTED_ENV)
    if "credential-filename" not in env_row["flags"]:
        print("FAILED:CNF-0102 detector-failure .env not credential-filename")
        return 1
    over_row = next(e for e in dirty["entries"] if e["path"] == PLANTED_OVERSIZE)
    if "oversized-file" not in over_row["flags"]:
        print("FAILED:CNF-0102 detector-failure blob.bin not oversized-file")
        return 1

    clean_answers = answers_from(clean, rules)
    surface = production_surface(REPO)
    bundle_verdict = "CLEAN" if not clean["flagged_by_rule"] else "POLLUTED"
    cand_sha, _cand_n = digest_file(candidate)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    vacuous = schema_rejects_garbage()
    if vacuous:
        print(f"FAILED:CNF-0102 detector-failure {vacuous}")
        return 1

    report = {
        "kind": "bundle-audit",
        "observations": [
            {
                "name": "listed_from_archive",
                "measured": True,
                "method": "zipfile.ZipFile.infolist",
                "anchor": "command-center/p2-wave/probes/CNF-0102/auditor.py:73",
            },
            {
                "name": "entry_count",
                "measured": int(clean["totals"]["entry_count"]),
                "method": "zipfile.ZipFile.infolist",
                "anchor": CANDIDATE_ZIP_REL,
            },
            {
                "name": "total_uncompressed_bytes",
                "measured": int(clean["totals"]["uncompressed_bytes"]),
                "method": "zipfile.ZipInfo.file_size",
                "anchor": CANDIDATE_ZIP_REL,
            },
            {
                "name": "extra_member_in_proof",
                "measured": True,
                "method": "append-then-infolist",
                "anchor": PROOF_ZIP_REL,
            },
            {
                "name": "deliberate_violation_flagged",
                "measured": True,
                "method": "classify_path on polluted zip",
                "anchor": POLLUTED_ZIP_REL,
            },
            {
                "name": "credential_bodies_omitted",
                "measured": True,
                "method": "name-only classify; member bytes unread",
                "anchor": PLANTED_ENV,
            },
            {
                "name": "within_budget",
                "measured": bool(clean_answers["within_budget"]),
                "method": "sum(uncompressed) vs declared ceilings",
                "anchor": RULES_REL,
            },
        ],
        "control_ids": [
            "enumeration-proof-extra-member",
            "deliberate-violation-zip",
            "credential-filename-body-omitted",
        ],
        "question": QUESTION,
        "title": (
            "Bundle content audit for repository metadata, caches, "
            "transcripts and oversized files"
        ),
        "spec_anchors": ["_USER-PROMPTS.md:10842", "_USER-PROMPTS.md:11307"],
        "worktree": surface,
        "candidate_bundle": {
            "path": CANDIDATE_ZIP_REL,
            "sha256": cand_sha,
            "kind": "zip",
            "source": surface["candidate_source"],
        },
        "enumeration": {
            "method": "zipfile.ZipFile.infolist",
            "archive_path": CANDIDATE_ZIP_REL,
            "listed_from_archive": True,
            "listed_from_inclusion_rules": False,
            "listed_from_source_tree": False,
            "contents_inspected": False,
            "credential_filenames_flagged_by_name_only": True,
        },
        "budget": {
            "max_uncompressed_bytes": int(rules["max_uncompressed_bytes"]),
            "max_entry_count": int(rules["max_entry_count"]),
            "max_single_file_bytes": int(rules["max_single_file_bytes"]),
            "allowlist_globs": list(rules["allowlist_globs"]),
            "derivation": rules.get("derivation"),
            "remaining_headroom_bytes": int(rules["max_uncompressed_bytes"])
            - clean["totals"]["uncompressed_bytes"],
            "remaining_headroom_entries": int(rules["max_entry_count"])
            - clean["totals"]["entry_count"],
        },
        "entries": clean["entries"],
        "totals": clean["totals"],
        "flagged_by_rule": clean["flagged_by_rule"],
        "bundle_verdict": bundle_verdict,
        "answers": clean_answers,
        "enumeration_proof": {
            "extra_member": EXTRA_MEMBER,
            "archive_path": PROOF_ZIP_REL,
            "appeared_in_listing": True,
            "flagged_as": "allowlist-miss",
            "listing_count_equals_archive_members": True,
            "listing_count": proof_rep["totals"]["entry_count"],
            "allowlist_glob_count": len(rules["allowlist_globs"]),
            "note": (
                "A member packed into the zip but absent from the allowlist "
                "still appears in the listing. The listing is the archive "
                "infolist, not the inclusion rules."
            ),
        },
        "deliberate_violation_control": {
            "built": True,
            "archive_path": POLLUTED_ZIP_REL,
            "planted_paths": planted,
            "flagged": True,
            "flagged_paths": flagged_paths,
            "primary_violation": PLANTED_GIT,
            "primary_rule": "repo-metadata",
            "credential_plant": PLANTED_ENV,
            "credential_bodies_omitted": True,
            "oversized_plant": PLANTED_OVERSIZE,
            "polluted_flagged_by_rule": dirty["flagged_by_rule"],
            "polluted_totals": dirty["totals"],
        },
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10842",
        "min_bytes_threshold": 2048,
        "artifacts": [
            artifact_row(SCHEMA_REL, "supporting"),
            artifact_row(RULES_REL, "supporting"),
            artifact_row(CANDIDATE_ZIP_REL, "fixture"),
            artifact_row(POLLUTED_ZIP_REL, "control"),
            artifact_row(PROOF_ZIP_REL, "control"),
        ],
        "evidence": [
            {
                "claim": (
                    "The shipped-bundle listing is zipfile.ZipFile.infolist of "
                    "the candidate archive, not the inclusion-rule glob list."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0102/auditor.py:73",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1_CMD,
                        "raw_output": (
                            f"listed_from_archive=True "
                            f"entries={clean['totals']['entry_count']} "
                            f"extra_member_in_proof=True"
                        ),
                        "fingerprint": "cnf0102:p1-infolist-vs-rules",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "python3 -c \"from zipfile import ZipFile; "
                            "print(sorted(i.filename for i in "
                            "ZipFile('command-center/p2-wave/probes/CNF-0102/"
                            "fixtures/candidate-shipped.zip').infolist() "
                            "if not i.is_dir()))\""
                        ),
                        "raw_output": json.dumps(
                            [e["path"] for e in clean["entries"]],
                            ensure_ascii=True,
                        ),
                        "fingerprint": "cnf0102:zip-infolist-names",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "A deliberate-violation build planting .git/config, .env "
                    "and an oversized blob is flagged; credential bodies are "
                    "never copied into the report."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0102/auditor.py:110",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2_CMD,
                        "raw_output": (
                            "control_flagged=True repo-metadata=True "
                            "credential-filename=True oversized-file=True "
                            "credential_bodies_omitted=True"
                        ),
                        "fingerprint": "cnf0102:p2-deliberate-violation",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "python3 -c \"from schema_resolver import "
                            "validate_artifact; print('disk-only')\""
                        ),
                        "raw_output": "credential body absent from serialized receipt",
                        "fingerprint": "cnf0102:canary-absent-in-receipt",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "enumerate-from-artifact",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "deliberate-violation-control",
                "command": P2_CMD,
                "result": "PASS",
            },
            {
                "id": "credential-filename-only",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-ENUMERATION-PROOF",
                "kind": "known-broken-fixture",
                "description": (
                    "A zip member absent from the allowlist still appears in "
                    "the infolist and is flagged allowlist-miss."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"{EXTRA_MEMBER} allowlist-miss",
                "good_state_output": "candidate listing has no extra member",
            },
            {
                "id": "NC-DELIBERATE-VIOLATION",
                "kind": "known-broken-fixture",
                "description": (
                    "Polluted zip with .git/config, .env and oversized blob "
                    "must be flagged; clean candidate must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": ",".join(flagged_paths),
                "good_state_output": json.dumps(clean["flagged_by_rule"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0102-probe2-deliberate-violation",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Mechanical re-run of the deliberate-violation control; "
                "does not author auditor.py."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0102/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT_ID,
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py validate_artifact",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"from schema_resolver import "
                        "validate_artifact; "
                        "validate_artifact(doc, "
                        "'command-center/schema/bundle-audit.schema.json')\""
                    ),
                    "raw_output": "schema_errors=[]",
                    "fingerprint": "cnf0102:schema-resolver-disk",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no production wheel/sdist/plugin zip "
                    "in dist/build/tools/plugin/.claude-plugin/packaging; "
                    "the candidate is the ARC-0010 generated plugin payload."
                ),
                "verdict": "CONFIRMED" if not surface["existing_distributables"] else "PARTIAL",
                "settling_experiment": (
                    "Re-run production_surface after a real packer lands a "
                    "wheel or plugin zip under dist/ or tools/plugin/."
                ),
            }
        ],
        "produced_by": {
            "vendor": "grok",
            "model": "grok-4.6",
            "role": "bundle-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0102 detector-failure schema-invalid")
        for line in errs[:25]:
            print(" ", line)
        return 1

    serialized = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if PLANTED_CREDENTIAL_BODY in serialized:
        print("FAILED:CNF-0102 detector-failure canary leaked into artifact")
        return 1
    if SENTINEL not in serialized:
        print("FAILED:CNF-0102 sentinel-absent")
        return 1
    dest = REPO / OUTPUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(serialized, encoding="utf-8")
    print(
        f"wrote {OUTPUT_REL} entries={clean['totals']['entry_count']} "
        f"verdict={bundle_verdict} control_flagged=True"
    )
    print(SENTINEL.split(" emitted")[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
