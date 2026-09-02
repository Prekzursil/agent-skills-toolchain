#!/usr/bin/env python3
"""Emit command-center/research/RES-0052.json from live measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import suite as S  # noqa: E402

OUT = "command-center/research/RES-0052.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
UNIT = "RES-0052"
QUESTION = (
    "What must a lockfile record for a package whose contents are files rather "
    "than resolved library versions (content hashes, source commit, resolution "
    "order), and does a re-install from the lockfile reproduce a byte-identical "
    "tree on Windows given CRLF normalization?"
)
SENTINEL = (
    "SUCCESS:RES-0052 in the receipt AND two installs whose per-file blob "
    "hashes match exactly, plus a demonstrated mismatch on mutation"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0052/probe1_reinstall_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0052/probe2_mutation_mismatch.py"
)


def main() -> int:
    report = S.run_suite()
    if not report["ok"]:
        print("FAILED:RES-0052 suite did not pass")
        print(json.dumps(report, indent=2, sort_keys=True, default=str)[:4000])
        return 1

    lock = report["lockfile"]
    identity = report["identity"]
    crlf = report["crlf_control"]
    mut = report["mutation"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_path = REPO / SCHEMA
    schema_present = schema_path.is_file()

    claims = [
        {
            "id": "C1-lockfile-fields",
            "claim": (
                "A lockfile for a file-package (prompts/scripts, not resolved "
                "library versions) must record per-file content hashes, the "
                "source commit, and a deterministic resolution order."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "anchor": "command-center/p2-wave/probes/RES-0052/lockfile.py:build_lockfile",
            "canonical_mechanism": (
                "content-addressed file lockfile hashed from git cat-file blobs"
            ),
        },
        {
            "id": "C2-reinstall-identity",
            "claim": (
                "Two installs from the same lockfile, writing `git cat-file -p` "
                "bytes in resolution order, produce trees whose per-file sha256 "
                "hashes match exactly."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "anchor": "command-center/p2-wave/probes/RES-0052/suite.py:identity",
            "measured": {
                "file_count": identity["file_count"],
                "trees_identical": identity["trees_identical"],
                "per_file_blob_hashes_match": identity["per_file_blob_hashes_match"],
                "hashes": identity["hashes_a"],
            },
        },
        {
            "id": "C3-archive-is-not-the-blob",
            "claim": (
                "`git archive` is not a blob-byte source when `text eol=crlf` is "
                "set: it emits CRLF while `git cat-file -p` and `git show` emit "
                "the LF blob. A lockfile hashed from archive bytes would fail "
                "byte-identity against the blob (the Windows autocrlf trap, "
                "reproduced on this Linux box via .gitattributes)."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "anchor": "command-center/p2-wave/probes/RES-0052/lockfile.py:three_route",
            "measured": {
                "archive_differs_on_any_file": crlf["archive_differs_on_any_file"],
                "files_where_archive_differs": crlf["files_where_archive_differs"],
                "any_archive_has_crlf": crlf["any_archive_has_crlf"],
                "any_blob_has_crlf": crlf["any_blob_has_crlf"],
                "cat_file_equals_show_all": crlf["cat_file_equals_show_all"],
                "routes": crlf["routes"],
            },
        },
        {
            "id": "C4-mutation-mismatch",
            "claim": (
                "Mutating one installed file makes compare_install report a "
                "mismatch. A silent always-match detector stays green in both "
                "states and is therefore not a measurement."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "anchor": "command-center/p2-wave/probes/RES-0052/suite.py:mutation",
            "measured": {
                "mutated_path": mut["mutated_path"],
                "before_match": mut["before_match"],
                "after_match": mut["after_match"],
                "after_mismatch_count": mut["after_mismatch_count"],
                "demonstrated_mismatch_on_mutation": mut[
                    "demonstrated_mismatch_on_mutation"
                ],
                "silent_detector_cannot_discriminate": mut[
                    "silent_detector_cannot_discriminate"
                ],
                "real_detector_discriminates": mut["real_detector_discriminates"],
            },
        },
        {
            "id": "C5-windows-byte-identity",
            "claim": (
                "Re-install byte-identity under CRLF normalization holds when "
                "the installer copies blob bytes from git cat-file, not when it "
                "copies git-archive or working-tree bytes. This box is Linux; "
                "the archive CRLF conversion was forced with `text eol=crlf`, "
                "which is the same git attribute Windows uses. PowerShell 7 vs "
                "Git Bash was not executed here."
            ),
            "verdict": "PARTIAL",
            "evidence_tier": "E1",
            "anchor": "command-center/p2-wave/probes/RES-0052/suite.py:crlf_control",
            "caveat": (
                "No Windows checkout and no PowerShell 7 reviewer. Tolerance "
                "on this box is exact (0) on counts, sizes, CRLF counts, and "
                "sha256 strings. A Windows worktree with core.autocrlf=true "
                "would still match if install writes cat-file bytes."
            ),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Design a lockfile that is reproducible for a non-code package "
            "of prompts and scripts"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "canonical_mechanism": (
            "content-addressed file lockfile: per-file sha256 of "
            "`git cat-file -p` blob bytes, source commit, NFC-sorted "
            "resolution order"
        ),
        "source_lineage": [
            {
                "kind": "catalog-row",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "unit_id": UNIT,
                "role": "question-and-tests-required",
            },
            {
                "kind": "live-measurement",
                "path": "command-center/p2-wave/probes/RES-0052/suite.py",
                "role": "both-states-install-and-crlf-control",
                "captured_at": now,
            },
            {
                "kind": "mature-registry-lockfile-shape",
                "note": (
                    "npm package-lock records tarball integrity (SRI) plus "
                    "resolved URL, not per-file hashes. poetry.lock records "
                    "distribution hashes plus a content-hash of the "
                    "declaration. cargo.lock records crate checksums. Those "
                    "are library-version locks. A prompts/scripts package has "
                    "no resolved library version, so the lock must name each "
                    "file, its blob digest, the source commit, and the order "
                    "files are written. Hashing a git-archive tarball would "
                    "bake in export-time CRLF and fail blob identity."
                ),
                "role": "contrast-not-copied",
            },
        ],
        "evidence_tier": "E1",
        "confidence_band": "high-on-this-box; Windows shell reviewer not run",
        "settling_probe": P1,
        "named_settling_probe": P1,
        "freshness": {"captured_at": now, "stamp": now},
        "snapshot_sha256": identity["hashes_a"],
        "claims": claims,
        "edges": {
            "supports": ["C1-lockfile-fields", "C2-reinstall-identity", "C4-mutation-mismatch"],
            "contradicts": [],
            "partial": ["C5-windows-byte-identity"],
        },
        "lockfile_design": {
            "kind": "file-package",
            "must_record": [
                "per-file path (NFC POSIX)",
                "per-file sha256 of git cat-file -p bytes",
                "per-file git blob sha1 and mode",
                "source_commit",
                "resolution_order",
            ],
            "must_not_record_as_identity": [
                "resolved library versions (none exist)",
                "git archive bytes",
                "working-tree bytes under autocrlf/eol=crlf",
            ],
            "byte_source": lock["byte_source"],
            "forbidden_byte_sources": lock["forbidden_byte_sources"],
            "lockfile": lock,
        },
        "tests": [
            {
                "id": "T1-two-installs",
                "command": P1,
                "result": "PASS" if identity["per_file_blob_hashes_match"] else "FAIL",
                "required": (
                    "install twice from the same lockfile and compare trees "
                    "hash by hash"
                ),
                "recorded_output": {
                    "fixture": "known-good",
                    "trees_identical": identity["trees_identical"],
                    "per_file_blob_hashes_match": identity[
                        "per_file_blob_hashes_match"
                    ],
                    "file_count": identity["file_count"],
                    "hashes_a": identity["hashes_a"],
                    "hashes_b": identity["hashes_b"],
                },
            },
            {
                "id": "T2-crlf-archive-vs-catfile",
                "command": P1,
                "result": "PASS" if crlf["archive_differs_on_any_file"] else "FAIL",
                "required": (
                    "CRLF control: prove the comparison uses blob bytes by "
                    "showing git archive and git cat-file differ"
                ),
                "recorded_output": {
                    "fixture": "known-good-blob / known-broken-archive-route",
                    "archive_differs_on_any_file": crlf[
                        "archive_differs_on_any_file"
                    ],
                    "any_archive_has_crlf": crlf["any_archive_has_crlf"],
                    "any_blob_has_crlf": crlf["any_blob_has_crlf"],
                    "cat_file_equals_show_all": crlf["cat_file_equals_show_all"],
                    "routes": crlf["routes"],
                },
            },
            {
                "id": "T3-mutation",
                "command": P2,
                "result": "PASS"
                if mut["demonstrated_mismatch_on_mutation"]
                else "FAIL",
                "required": (
                    "negative control: mutate one file and confirm the "
                    "comparison reports a mismatch"
                ),
                "recorded_output": {
                    "fixture": "known-broken-mutation",
                    "known_good_before": mut["before_match"],
                    "known_broken_after": not mut["after_match"],
                    "mutated_path": mut["mutated_path"],
                    "after_mismatch_count": mut["after_mismatch_count"],
                    "after_mismatches": mut["after_mismatches"],
                    "silent_detector_both_states_green": mut[
                        "silent_detector_cannot_discriminate"
                    ],
                },
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0052-probe2-mutation-mismatch",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "shell": "Linux bash + a second Python process (probe2)",
            "powershell7_vs_git_bash": "NOT-CHECKED — PowerShell 7 is not on this Linux worktree",
            "tolerance": "exact match (0) on file counts, byte sizes, CRLF counts, sha256",
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0052/lockfile.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0052/suite.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "schema_residual": (
            None
            if schema_present
            else (
                "command-center/schema/research-claim-record.schema.json is "
                "absent on this worktree (RES-0001). This record carries the "
                "RES-0001 field set (source_lineage, evidence_tier, "
                "canonical_mechanism, settling_probe, freshness, "
                "snapshot_sha256) and is not self-declared BLOCKED."
            )
        ),
        "strongest_surviving_counterargument": (
            "This measurement ran on Linux. git archive emitted CRLF because "
            "the fixture set `text eol=crlf`, which is the conversion git "
            "archive applies on Windows as well, but a PowerShell 7 vs Git "
            "Bash re-run on a real Windows checkout was not performed. "
            "C5 is therefore PARTIAL, not a Windows-end-to-end confirmation."
        ),
        "residual_unknowns": [
            "PowerShell 7 vs Git Bash reviewer not executed on this box.",
            "research-claim-record.schema.json not on disk (RES-0001).",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "two_installs_per_file_blob_hashes_match_exactly": identity[
            "per_file_blob_hashes_match"
        ],
        "demonstrated_mismatch_on_mutation": mut[
            "demonstrated_mismatch_on_mutation"
        ],
        "captured_at": now,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0052 sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
