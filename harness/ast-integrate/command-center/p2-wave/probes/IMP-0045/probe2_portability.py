#!/usr/bin/env python3
"""Probe 2 (reviewer): blob hashing, not worktree, not git archive.

Two independent signals over the SAME tree SHA:
  (1) Linux/LF worktree materialisation
  (2) Windows/CRLF worktree materialisation (the autocrlf=true replica)

Conformance must agree (identical verdict_digest) because it hashes via
git cat-file. Raw worktree sha256 of plugin.json MUST differ, proving the
control is live and that hashing worktree bytes would reintroduce the
split verdict this unit exists to close.

A real Microsoft Windows runner is residual NOT-CHECKED; the defect class
named in the catalog is crlf-phantom-drift, and that class is closed here.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loader import SENTINEL, blob_sha, load_mod, load_receipt, worktree_sha  # noqa: E402

B = load_mod("blob")
F = load_mod("fixture_tree")
C = load_mod("conformance")


def source_forbids_archive() -> dict:
    blob_src = (HERE.parents[3] / "tools" / "plugin" / "blob.py").read_text(encoding="utf-8")
    conf_src = (HERE.parents[3] / "tools" / "plugin" / "conformance.py").read_text(
        encoding="utf-8"
    )
    # Mentions are allowed. Invocations through _git() must refuse.
    blob_calls_archive = "git archive" in blob_src and "FORBIDDEN" in blob_src
    return {
        "blob_py_names_archive_only_as_forbidden": blob_calls_archive,
        "conformance_py_has_no_archive_argv": "archive" not in conf_src.split("HASH_ROUTE")[0]
        or "forbidden" in conf_src.lower(),
        "hash_route_constant": C.HASH_ROUTE,
    }


def main() -> int:
    rec = load_receipt()
    if rec.get("unit_id") != "IMP-0045":
        print("FAILED:IMP-0045-probe2 unit_id", rec.get("unit_id"))
        return 1

    td = Path(tempfile.mkdtemp(prefix="imp0045-p2-"))
    git_dir, tree = F.build_tree(F.good_files(), td / "store")
    spec = f"{tree}:plugin.json"
    blob = B.blob_bytes(git_dir, tree, "plugin.json")
    if b"\r\n" in blob:
        print("FAILED:IMP-0045-probe2 blob itself contains CRLF")
        return 1
    if not B.show_equals_cat(git_dir, spec):
        print("FAILED:IMP-0045-probe2 git show != git cat-file")
        return 1
    try:
        B._git(git_dir, "archive", "--format=tar", tree)
        print("FAILED:IMP-0045-probe2 _git allowed archive")
        return 1
    except B.BlobRouteError:
        pass

    arch = B.archive_bytes(git_dir, tree, "plugin.json")
    # On Linux archive often equals the blob; that does NOT license using it.
    archive_equals_blob = arch == blob

    lf_root = td / "wt-lf"
    crlf_root = td / "wt-crlf"
    st_lf = B.materialize(git_dir, tree, lf_root, eol="lf")
    st_crlf = B.materialize(git_dir, tree, crlf_root, eol="crlf")
    lf_plugin = lf_root / "plugin.json"
    crlf_plugin = crlf_root / "plugin.json"
    wt_lf = worktree_sha(lf_plugin)
    wt_crlf = worktree_sha(crlf_plugin)
    if wt_lf == wt_crlf:
        print("FAILED:IMP-0045-probe2 worktree hashes did not diverge (control inert)")
        return 1
    if blob_sha(blob) == wt_crlf:
        print("FAILED:IMP-0045-probe2 CRLF worktree hash accidentally equals blob")
        return 1
    if blob_sha(blob) != wt_lf:
        # LF worktree of an LF blob should match; if not, materialize is wrong.
        print("FAILED:IMP-0045-probe2 LF worktree != blob (unexpected on this box)")
        return 1

    linux = C.run_conformance(git_dir, tree, worktree=lf_root)
    windows = C.run_conformance(git_dir, tree, worktree=crlf_root)
    if linux["verdict"] != "PASS" or windows["verdict"] != "PASS":
        print("FAILED:IMP-0045-probe2 conformance not PASS on both eol regimes")
        print(linux["violations"], windows["violations"])
        return 1
    if linux["verdict_digest"] != windows["verdict_digest"]:
        print("FAILED:IMP-0045-probe2 split verdict across LF/CRLF worktrees")
        print(linux["verdict_digest"], windows["verdict_digest"])
        return 1
    if linux["hash_route"] != C.HASH_ROUTE or windows["hash_route"] != C.HASH_ROUTE:
        print("FAILED:IMP-0045-probe2 hash_route drifted")
        return 1

    # Negative control: hashing worktree bytes WOULD split.
    if hashlib.sha256(lf_plugin.read_bytes()).hexdigest() == hashlib.sha256(
        crlf_plugin.read_bytes()
    ).hexdigest():
        print("FAILED:IMP-0045-probe2 worktree-hash negative control inert")
        return 1

    src = source_forbids_archive()
    summary = {
        "probe": "probe2-portability-blob-route",
        "unit_id": "IMP-0045",
        "tree": tree,
        "blob_sha256": blob_sha(blob),
        "blob_bytes": len(blob),
        "blob_crlf": blob.count(b"\r\n"),
        "git_show_equals_cat_file": True,
        "archive_equals_blob_on_this_os": archive_equals_blob,
        "archive_refused_as_hash_route": True,
        "worktree_lf_sha256": wt_lf,
        "worktree_crlf_sha256": wt_crlf,
        "worktree_hashes_diverge": True,
        "linux_lf_digest": linux["verdict_digest"],
        "windows_crlf_digest": windows["verdict_digest"],
        "digests_agree": True,
        "hash_route": linux["hash_route"],
        "materialize_lf": st_lf,
        "materialize_crlf": st_crlf,
        "source_guard": src,
        "windows_runner": "NOT-CHECKED (CRLF replica on Linux; defect class closed)",
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"digest_agree=True worktree_diverge=True archive_refused=True "
        f"archive_eq_blob={archive_equals_blob}"
    )
    print(f"SUCCESS:IMP-0045-probe2 blob-route portability {SENTINEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
