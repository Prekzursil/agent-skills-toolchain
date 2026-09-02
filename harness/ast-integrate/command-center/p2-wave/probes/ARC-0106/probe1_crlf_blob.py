#!/usr/bin/env python3
"""Probe 1: CRLF both-states + git cat-file -p vs git archive + UTF-8 BOM.

Line-ending behaviour is taken from git cat-file -p (the blob), never from
git archive. Both readings are recorded. The worktree itself is not a git
repo; the method is proved on a throwaway lab repository.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hostility as H  # noqa: E402

OUT = HERE / "probe1-crlf.raw.json"


def main() -> int:
    snap = H.measure_probe1()
    OUT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    blob = snap["blob_method"]
    crlf = snap["crlf_both_states"]
    bom = snap["bom_both_states"]
    wt = snap["worktree_git"]
    if not blob.get("ok"):
        print("FAILED:ARC-0106-probe1 blob-method lab repo failed", blob)
        return 1
    readings = blob.get("readings") or {}
    if "git cat-file -p" not in readings or "git archive" not in readings:
        print("FAILED:ARC-0106-probe1 both git readings not shown")
        return 1
    if not blob.get("never_git_archive_for_blob"):
        print("FAILED:ARC-0106-probe1 archive used as blob source")
        return 1
    if not blob.get("working_tree_crlf_shown"):
        print("FAILED:ARC-0106-probe1 working-tree CRLF reading missing")
        return 1
    if not crlf.get("both_verdicts_recorded"):
        print("FAILED:ARC-0106-probe1 CRLF both-states not recorded")
        return 1
    if "validate_lf_blob" not in crlf or "validate_crlf_working_tree" not in crlf:
        print("FAILED:ARC-0106-probe1 validator verdicts missing")
        return 1
    if "without_bom" not in bom or "with_bom" not in bom:
        print("FAILED:ARC-0106-probe1 BOM both-states missing")
        return 1
    cat_r = readings["git cat-file -p"]
    arch_r = readings["git archive"]
    print(
        "worktree_git="
        + str(wt.get("is_git_repo"))
        + " cat-file_bytes="
        + str(cat_r.get("bytes"))
        + " cat-file_crlf="
        + str(cat_r.get("crlf"))
        + " archive_bytes="
        + str(arch_r.get("bytes"))
        + " archive_crlf="
        + str(arch_r.get("crlf"))
        + " archive_equals_blob="
        + str(blob.get("archive_equals_blob"))
        + " wt_crlf_differs="
        + str(blob.get("working_tree_differs_from_blob"))
        + " validate_lf_reach6_clean="
        + str(crlf["validate_lf_blob"]["clean_reach6"])
        + " validate_crlf_reach6_clean="
        + str(crlf["validate_crlf_working_tree"]["clean_reach6"])
        + " seed_matches_lf_blob="
        + str(crlf.get("seed_matches_lf_blob_digest"))
        + " um_survives_crlf="
        + str(crlf["unit_manifest"]["survives_crlf"])
        + " catalog_load_breaks_on_bom="
        + str(bom.get("catalog_load_breaks_on_bom"))
    )
    print("SUCCESS:ARC-0106-probe1 crlf-blob-bom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
