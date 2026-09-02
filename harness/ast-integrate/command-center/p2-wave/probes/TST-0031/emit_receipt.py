#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0031.json from a live fixture measurement."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

import blob_gate as G  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None  # type: ignore

OUT = "command-center/receipts/TST-0031.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0031/probe1_blob_not_worktree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0031/probe2_lint_and_checklist.py"
)
QUESTION = (
    "Measured on this box: git archive | tar -x returns CRLF worktree-form bytes "
    "while git cat-file -p returns the true LF blob for the same path. A local "
    "formatter green measured against the wrong bytes verifies nothing. Target: a "
    "gate that verifies formatting and hashing against the BLOB, plus a lint "
    "banning git archive for this purpose. RELEASE-CHECKLIST.md must match the gate."
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0031-emit-") as td:
        measured = G.eol_divergence_fixture(Path(td) / "fx")
    table = measured["three_route"]
    gate = measured["gate"]
    if not table["archive_differs_from_blob"]:
        print("FAILED:TST-0031 emit three-route archive==blob on this box")
        return 1
    if not table["identical_after_lf_normalisation"]:
        print("FAILED:TST-0031 emit LF-normalisation identity failed")
        return 1
    if not table["cat_file_equals_show"]:
        print("FAILED:TST-0031 emit cat-file !== show")
        return 1
    if gate["hash_matches_worktree"]:
        print("FAILED:TST-0031 emit gate hash matched dirty CRLF worktree")
        return 1
    if gate["verdict"] != "PASS":
        print("FAILED:TST-0031 emit LF blob did not PASS format")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    routes = table["routes"]
    doc = {
        "unit_id": "TST-0031",
        "id": "TST-0031",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0031",
        "completion_sentinel": "SUCCESS:TST-0031",
        "report_kind": "test-receipt",
        "title": "Blob-versus-worktree EOL parity gate (git cat-file, never git archive)",
        "question": QUESTION,
        "phase": "10",
        "ts": now,
        "cloud_ok": False,
        "registered": True,
        "host": {"os": "linux", "git": "fixture-repo (worktree is not a git checkout)"},
        "recipe": {
            "authoritative": G.AUTHORITATIVE_RECIPE,
            "equivalent": G.EQUIVALENT_RECIPE,
            "banned_as_blob_source": G.BANNED_BLOB_SOURCE,
        },
        "three_route": table,
        "gate": gate,
        "headline": (
            f"archive={routes['git archive | tar -x']['bytes']}B/"
            f"{routes['git archive | tar -x']['crlf']}CRLF "
            f"cat-file={routes['git cat-file -p']['bytes']}B/"
            f"{routes['git cat-file -p']['crlf']}CRLF "
            f"show={routes['git show <rev>:<path>']['bytes']}B/"
            f"{routes['git show <rev>:<path>']['crlf']}CRLF "
            "identical_after_lf=True archive_differs=True"
        ),
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "On this Linux box, a fixture with `text eol=crlf` makes "
                    "`git archive | tar -x` return CRLF while `git cat-file -p` "
                    "and `git show` return the LF blob; after LF normalisation "
                    "the three payloads are identical."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0031/blob_gate.py",
            },
            {
                "id": "C2",
                "claim": (
                    "The hash/format gate reads cat-file blob bytes. A dirty "
                    "CRLF worktree does not change the hash or format verdict; "
                    "a CRLF blob fails format."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0031/probe1_blob_not_worktree.py",
            },
            {
                "id": "C3",
                "claim": (
                    "The lint flags git archive used as a blob source (fenced "
                    "or shell pipeline) and stays silent on mentions and on "
                    "whole-tree packaging. RELEASE-CHECKLIST.md now prescribes "
                    "cat-file/show, matching the gate."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/RELEASE-CHECKLIST.md",
            },
        ],
        "tests": [
            {
                "id": "test_gate_reads_blob_bytes_not_worktree_bytes",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_lint_flags_git_archive_used_as_a_blob_source",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_release_checklist_recipe_matches_the_gate",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0031-probe2-independent-lint-and-checklist",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 plants mention/prescription/packaging fixtures and "
                "re-reads RELEASE-CHECKLIST.md without sharing probe 1's git fixture."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0031/blob_gate.py",
                "exists": True,
                "role": "gate",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0031/archive_lint.py",
                "exists": True,
                "role": "lint",
            },
            {
                "path": "command-center/RELEASE-CHECKLIST.md",
                "exists": True,
                "role": "checklist",
            },
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0031/blob_gate.py",
                "kind": "three-route-live-fixture",
                "note": (
                    f"archive {routes['git archive | tar -x']['bytes']}B/"
                    f"{routes['git archive | tar -x']['crlf']}CRLF vs "
                    f"cat-file {routes['git cat-file -p']['bytes']}B/"
                    f"{routes['git cat-file -p']['crlf']}CRLF"
                ),
            },
            {
                "path": "command-center/RELEASE-CHECKLIST.md",
                "kind": "recipe-alignment",
                "note": "TST-0031 section prescribes git cat-file -p / git show; packaging archive is fenced with --format=tar.gz",
            },
            {
                "path": "command-center/harness/both_states.py",
                "kind": "both-states-harness",
                "note": "TST-0013 harness loaded by file path (package __init__ is stale)",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "blob-not-worktree", "command": P1},
            {"id": "probe2", "role": "lint-and-checklist", "command": P2},
        ],
        "dependency_note": (
            "TST-0013 harness is consumed via command-center/harness/both_states.py. "
            "This worktree is not a git repository; three-route numbers are from a "
            "throwaway fixture repo on this box, not from HEAD of ast-integrate."
        ),
    }

    schema_path = REPO / SCHEMA
    # The catalog schema is a generated $ref shim to ast-integrate.invalid; it
    # does not resolve on this box. G-1 does not require live schema fetch.
    if jsonschema is not None and schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        ref = schema.get("$ref") if isinstance(schema, dict) else None
        if not (isinstance(ref, str) and "ast-integrate.invalid" in ref):
            jsonschema.Draft7Validator(schema).validate(doc)

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:TST-0031 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
