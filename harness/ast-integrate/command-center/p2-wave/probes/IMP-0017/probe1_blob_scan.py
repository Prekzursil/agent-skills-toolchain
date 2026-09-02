#!/usr/bin/env python3
"""Probe 1: git cat-file -p blob CR scan; worktree is not the oracle.

Mutation: without *.sh eol=lf, a CRLF file lands in the blob and the
blob-level test goes red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN / "tests"))
sys.path.insert(0, str(PLUGIN))

import eol_assert as E  # noqa: E402
import test_eol_policy as tests  # noqa: E402

OUT = HERE / "probe1-blob-scan.raw.json"


def main() -> int:
    blob = tests.test_no_cr_in_shipped_shell_blobs()
    mut = tests.test_gitattributes_mutation_detected_by_blob_scan()
    gat = (REPO / ".gitattributes").read_text(encoding="utf-8")
    missing = E.missing_eol_lf_patterns(gat)
    src = (PLUGIN / "pack.py").read_text(encoding="utf-8")
    uses_archive = "git archive" in src
    uses_cat = "cat-file" in src
    payload = {
        "probe": "probe1-blob-scan",
        "unit_id": "IMP-0017",
        "pass": True,
        "reader": "git cat-file -p",
        "worktree_is_not_oracle": bool(blob["worktree_cr"]) and not blob["blob_cr"],
        "product_gitattributes_missing": missing,
        "packer_source_contains_git_archive": uses_archive,
        "packer_source_contains_cat_file": uses_cat,
        "blob_scan": blob,
        "mutation": mut,
    }
    if missing or uses_archive or not uses_cat or not payload["worktree_is_not_oracle"]:
        payload["pass"] = False
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        print("FAILED:IMP-0017-probe1")
        return 1
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(
        f"shell_blobs={blob['shell_blobs']} worktree_cr=True blob_cr=False "
        f"mutation_hits={mut['hits']} missing={missing}"
    )
    print("SUCCESS:IMP-0017-probe1 blob cat-file scan and gitattributes mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
