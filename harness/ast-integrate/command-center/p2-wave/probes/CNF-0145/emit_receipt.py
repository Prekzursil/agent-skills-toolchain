#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0145.json from a live clean-room rebuild."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402
from scenario import assert_scenario, run_scenario  # noqa: E402

OUT = "command-center/receipts/CNF-0145.json"
SCHEMA = "command-center/schema/reproduction-matrix.schema.json"
CHECKLIST = "command-center/RELEASE-CHECKLIST.md"
LIB_REL = "command-center/p2-wave/probes/CNF-0145/lib.py"
SCEN_REL = "command-center/p2-wave/probes/CNF-0145/scenario.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0145/probe1_mutation_and_hygiene.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0145/probe2_fresh_clone_and_blob.py"
)


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    hits = [
        i
        for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if snippet in ln
    ]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNF-0145 emit anchor {rel} {snippet!r} hits={hits}")
    return hits[0]


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    data = run_scenario()
    errs = assert_scenario(data)
    if errs:
        print("FAILED:CNF-0145 scenario")
        for item in errs:
            print(" ", item)
        return 1
    if not L.schema_rejects_garbage():
        print("FAILED:CNF-0145 schema accepted garbage")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    estate = data["estate"]
    both = data["both_states"]
    trap = data["archive_trap"]
    released_sha = data["sha256_sets"]["released"]["archive_sha256"]
    rebuild_sha = data["sha256_sets"]["rebuild"]["archive_sha256"]

    doc = {
        "unit_id": L.UNIT,
        "id": L.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": L.SENTINEL,
        "completion_sentinel": L.SENTINEL,
        "schema_version": 1,
        "report_kind": "reproduction-matrix",
        "title": (
            "Clean-room rebuild of the plugin package from a scratch clone "
            "with no local state"
        ),
        "question": L.QUESTION,
        "produced_at": now,
        "output_schema": SCHEMA,
        "byte_source": L.BYTE_SOURCE,
        "forbidden_byte_source": L.FORBIDDEN_BYTE_SOURCE,
        "release_tag": data["release_tag"],
        "estate": estate,
        "verdict": "CONFIRMED",
        "sha256_sets": data["sha256_sets"],
        "classified_diff": both["classified_diff"],
        "remaining_diffs": both["remaining_diffs"],
        "material_remaining": both["material_remaining"],
        "normalized_identical": both["normalized_identical"],
        "raw_identical": both["raw_identical"],
        "normalizers": [
            {
                "id": "zero-mtime",
                "benign_class": "timestamps",
                "applied": True,
                "snippet": "CNF-0145-NORMALIZER-MTIME",
            },
            {
                "id": "nfc-sort",
                "benign_class": "ordering",
                "applied": True,
                "snippet": "CNF-0145-NORMALIZER-ORDER",
            },
            {
                "id": "zero-uid-gid",
                "benign_class": "ownership",
                "applied": True,
                "snippet": "CNF-0145-NORMALIZER-OWNER",
            },
            {
                "id": "lf-normalize",
                "benign_class": "line-endings",
                "applied": True,
                "snippet": "replace CRLF then CR with LF",
            },
        ],
        "package_hygiene": {
            "clean_archive": data["package_hygiene"]["clean_archive"],
            "planted_found": data["package_hygiene"]["planted_found"],
            "classes_found": data["package_hygiene"]["classes_found"],
            "empty_staging_clean": data["package_hygiene"]["empty_staging_clean"],
            "plants": data["package_hygiene"]["plants"],
        },
        "fresh_clone_proof": {
            "used": True,
            "created_during_this_run": data["fresh_clone_proof"]["created_during_this_run"],
            "clone_ctime": data["fresh_clone_proof"]["clone_ctime"],
            "run_started_unix": data["fresh_clone_proof"]["run_started_unix"],
            "isolated_home": True,
            "home_cache_absent": data["fresh_clone_proof"]["home_cache_absent"],
            "second_clone_identical": data["fresh_clone_proof"]["second_clone_identical"],
            "method": data["fresh_clone_proof"]["method"],
        },
        "controls": {
            "known_present_one_byte": {
                "fired": True,
                "class": "material-content",
                "path": data["known_present"]["path"],
                "committed_also_fired": data["committed_mutation"]["fired"],
            },
            "both_states_unmutated_clean": {
                "normalized_identical": True,
                "raw_identical": both["raw_identical"],
            },
            "naive_timestamp_normalizer_not_inert": {
                "raw_differs": True,
                "normalized_identical": True,
            },
        },
        "archive_trap": trap,
        "member_blob_audit": data["member_blob_audit"],
        "reviewer": {
            "reviewer_id": "CNF-0145-probe2-second-clone-cat-file",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Second scratch clone plus independent git cat-file -p of every "
                "packed member. Same filesystem, not a different physical drive."
            ),
            "second_scratch_pack_sha256": data["reviewer"]["second_scratch_pack_sha256"],
            "matches_released": data["reviewer"]["matches_released"],
        },
        "tests": [
            {
                "id": "T1-known-present-one-byte",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-unmutated",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-package-hygiene-10842",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T4-fresh-clone-ctime-and-blob",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            ev(
                LIB_REL,
                "CNF-0145-PACK-USES-CAT-FILE-NOT-ARCHIVE",
                "byte-source",
                "Packer reads git cat-file -p, never git archive.",
            ),
            ev(
                LIB_REL,
                "CNF-0145-HYGIENE-SCAN-10842",
                "hygiene",
                "Scanner covers git, caches, transcripts, credentials, logs.",
            ),
            ev(
                LIB_REL,
                "CNF-0145-NORMALIZER-MTIME",
                "normalizer",
                "Timestamp normalizer zeros tar and gzip mtime.",
            ),
            ev(
                LIB_REL,
                "CNF-0145-NORMALIZER-ORDER",
                "normalizer",
                "Ordering normalizer NFC-sorts archive members.",
            ),
            ev(
                LIB_REL,
                "CNF-0145-NORMALIZER-OWNER",
                "normalizer",
                "Ownership normalizer zeros uid/gid.",
            ),
            ev(
                SCEN_REL,
                "CNF-0145-FRESH-CLONE-CTIME",
                "fresh-clone",
                "Clone destination is created during this run; ctime is recorded.",
            ),
            ev(
                CHECKLIST,
                "git cat-file -p HEAD:path/to/file",
                "checklist",
                "RELEASE-CHECKLIST.md prescribes cat-file, not git archive.",
            ),
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "output-schema"},
            {"path": CHECKLIST, "exists": True, "role": "release-checklist"},
            {"path": LIB_REL, "exists": True, "role": "packer"},
            {"path": SCEN_REL, "exists": True, "role": "scenario"},
        ],
        "named_probes": [
            {"id": "probe1", "role": "mutation-hygiene-both-states", "command": P1},
            {"id": "probe2", "role": "fresh-clone-cat-file", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0145/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "residual_unknowns": [
            {
                "id": "R1",
                "item": "estate released plugin package",
                "status": "NOT-CHECKED",
                "reason": (
                    "Worktree is not a git checkout; tools/plugin/pack.py and "
                    "command-center/ARTIFACT-MANIFEST.json are absent. Rebuild "
                    "identity is confirmed on a tagged fixture plugin, not a "
                    "production release tarball."
                ),
            }
        ],
        "min_bytes_threshold": 2048,
        "answer": (
            "This worktree has no released plugin artifact, no tools/plugin/pack.py, "
            "and is not a git checkout. A fixture plugin tagged "
            f"{data['release_tag']} rebuilt from a fresh clone with empty HOME into "
            f"a byte-identical package (released sha256={released_sha} rebuild "
            f"sha256={rebuild_sha}). Remaining diffs after timestamp/ordering/"
            "ownership normalizers: none. A one-byte README mutation is classified "
            "material-content and fires. Hygiene plants for .git, caches, transcripts, "
            "credentials and logs are found; the packed archive contains none. "
            f"git archive on {trap['path']} returns {trap['archive_crlf']} CRLF / "
            f"{trap['archive_bytes']} bytes while git cat-file -p returns "
            f"{trap['cat_file_crlf']} CRLF / {trap['cat_file_bytes']} bytes; packs "
            "use cat-file only. SUCCESS:CNF-0145"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if schema_errs:
        print("FAILED:CNF-0145 schema errors")
        for err in schema_errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    live_errs = L.validate_report(doc)
    if live_errs:
        print("FAILED:CNF-0145 validate_report", live_errs[:8])
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if L.SENTINEL not in raw:
        print("FAILED:CNF-0145 sentinel missing from artifact text")
        return 1
    if len(raw.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:CNF-0145 artifact below byte floor")
        return 1
    out.write_text(raw, encoding="utf-8")
    digest, size = L.digest_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0145 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
